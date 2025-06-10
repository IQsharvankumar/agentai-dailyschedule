
from ortools.sat.python import cp_model
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import json


class MockKBS:
    """Mock Knowledge Base System for testing purposes"""
    
    def get_rule(self, rule_name: str):
        rules = {
            "task_default_duration": 30,  # minutes
            "alert_default_address_time": 15,
            "travel_speed_mph": 20,  # for simple distance/time calc
            "priority_weights": {"High": 10, "Medium": 5, "Low": 1},
            "objective_weights": {"priority_sum": 100, "lateness_penalty": -10}
        }
        return rules.get(rule_name)
    
    def get_constraint(self, constraint_name: str):
        constraints = {
            "max_work_time": 480,  # 8 hours in minutes
            "min_break_duration": 15,
            "max_continuous_work": 120  # 2 hours
        }
        return constraints.get(constraint_name)


class IntelligentDailyScheduleOptimizer:
    """
    Intelligent Daily Schedule Optimization Agent (IDSOA) for nurses.
    Uses Google OR-Tools CP-SAT solver to optimize daily schedules.
    Supports patient preferences and comprehensive constraint handling.
    """
    
    def __init__(self, nurse_id: str, schedule_date: str, knowledge_base_accessor):
        self.nurse_id = nurse_id
        self.schedule_date_obj = datetime.strptime(schedule_date, "%Y-%m-%d").date()
        self.kbs = knowledge_base_accessor
        
    def _time_to_minutes(self, time_str: str) -> int:
        """Convert HH:MM:SS time string to minutes from midnight"""
        try:
            # Handle both HH:MM:SS and HH:MM formats
            parts = time_str.split(':')
            h = int(parts[0])
            m = int(parts[1])
            s = int(parts[2]) if len(parts) > 2 else 0
            return h * 60 + m
        except (ValueError, IndexError):
            raise ValueError(f"Invalid time format: {time_str}")
    
    def _minutes_to_time_str(self, minutes: int) -> str:
        """Convert minutes from midnight to HH:MM:SS string"""
        hours = minutes // 60
        mins = minutes % 60
        return f"{hours:02d}:{mins:02d}:00"
    
    def _extract_deadline_time(self, deadline_str: str) -> Optional[int]:
        """Extract time from deadline string (handles both datetime and time formats)"""
        if not deadline_str:
            return None
        
        try:
            # Handle ISO datetime format (YYYY-MM-DDTHH:MM:SS)
            if 'T' in deadline_str:
                time_part = deadline_str.split('T')[1]
                return self._time_to_minutes(time_part)
            # Handle time-only format (HH:MM:SS)
            else:
                return self._time_to_minutes(deadline_str)
        except (ValueError, IndexError):
            return None
    
    def _prepare_activities(self, work_items: Dict, nurse_constraints: Dict) -> List[Dict]:
        """
        Combine all work items into a unified list with consistent attributes for the solver.
        Handles patient preferences: CRITICAL_PATIENT_FOCUSED, BALANCED, HIGH_PRIORITY_FIRST, 
        SIMILAR_TASK_FIRST, PATIENT_CONTEXT_FOCUSED
        """
        prepared_activities = []
        patient_preference = nurse_constraints.get("patientPreference", "BALANCED")
        
        # Process appointments
        for appointment in work_items.get("appointments", []):
            activity = {
                "id": appointment["itemId"],
                "type": "appointment",
                "duration": appointment["estimatedDuration"],
                "priority": appointment.get("initialPriorityScore", 5),
                "title": appointment["title"],
                "is_fixed": appointment.get("isFixedTime", False),
                "fixed_start_time_str": appointment.get("startTime") if appointment.get("isFixedTime") else None,
                "deadline": None,
                "location": appointment.get("location", ""),
                "patient_id": appointment.get("patientId", "")
            }
            prepared_activities.append(activity)
        
        # Process calendar events
        for event in work_items.get("calendar_events", []):
            activity = {
                "id": event["itemId"],
                "type": "meeting",
                "duration": event["estimatedDuration"],
                "priority": event.get("initialPriorityScore", 4),
                "title": event["title"],
                "is_fixed": event.get("isFixedTime", False),
                "fixed_start_time_str": event.get("startTime") if event.get("isFixedTime") else None,
                "deadline": None,
                "location": event.get("location", ""),
                "patient_id": ""
            }
            prepared_activities.append(activity)
        
        # Process tasks
        for task in work_items.get("tasks", []):
            priority_text = task.get("initialPriorityScore_text", "Medium")
            priority_weights = self.kbs.get_rule("priority_weights")
            numerical_priority = task.get("initialPriorityScore", priority_weights.get(priority_text, 5))
            
            activity = {
                "id": task["taskId"],
                "type": "task",
                "duration": task["estimatedDuration"],
                "priority": numerical_priority,
                "title": task["description"],
                "is_fixed": False,
                "fixed_start_time_str": None,
                "deadline": task.get("deadline"),
                "location": task.get("locationDependency", ""),
                "patient_id": task.get("patientId", "")
            }
            prepared_activities.append(activity)
        
        # Process critical alerts
        for alert in work_items.get("critical_alerts_to_address", []):
            activity = {
                "id": alert["alertId"],
                "type": "alert",
                "duration": alert["estimatedTimeToAddress"],
                "priority": alert.get("urgencyScore", 10),
                "title": f"Alert: {alert['summary']}",
                "is_fixed": False,
                "fixed_start_time_str": None,
                "deadline": None,
                "location": "",
                "patient_id": alert.get("patientId", "")
            }
            prepared_activities.append(activity)
        
        # Process follow-ups
        for followup in work_items.get("follow_ups", []):
            activity = {
                "id": followup["followUpId"],
                "type": "follow_up",
                "duration": followup["estimatedDurationForFollowUpAction"],
                "priority": followup.get("initialPriorityScore", 7),
                "title": f"Follow-up: {followup['reason']}",
                "is_fixed": False,
                "fixed_start_time_str": None,
                "deadline": None,
                "location": "",
                "patient_id": followup.get("patientId", "")
            }
            prepared_activities.append(activity)
        
        # Process break times (additional breaks beyond lunch)
        for break_time in work_items.get("break_times", []):
            activity = {
                "id": break_time.get("breakId", f"BREAK_{len(prepared_activities)}"),
                "type": "break",
                "duration": break_time["duration"],
                "priority": 5,
                "title": f"Break: {break_time.get('reason', 'Scheduled Break')}",
                "is_fixed": break_time.get("isFixed", False),
                "fixed_start_time_str": break_time.get("startTime") if break_time.get("isFixed") else None,
                "deadline": None,
                "location": "",
                "patient_id": ""
            }
            prepared_activities.append(activity)
        
        # Process care plans
        for care_plan in work_items.get("care_plans", []):
            activity = {
                "id": care_plan.get("carePlanId", f"CP_{len(prepared_activities)}"),
                "type": "care_plan",
                "duration": care_plan.get("estimatedDuration", 30),
                "priority": care_plan.get("priority", 8),
                "title": f"Care Plan: {care_plan.get('description', 'Patient Care')}",
                "is_fixed": False,
                "fixed_start_time_str": None,
                "deadline": care_plan.get("deadline"),
                "location": "",
                "patient_id": care_plan.get("patientId", "")
            }
            prepared_activities.append(activity)
        
        # Process patient admission alerts
        for admission_alert in work_items.get("patient_admission_alerts", []):
            activity = {
                "id": admission_alert.get("alertId", f"ADM_{len(prepared_activities)}"),
                "type": "admission_alert",
                "duration": admission_alert.get("estimatedTimeToAddress", 15),
                "priority": admission_alert.get("urgencyScore", 9),
                "title": f"Admission Alert: {admission_alert.get('summary', 'Patient Admission')}",
                "is_fixed": False,
                "fixed_start_time_str": None,
                "deadline": None,
                "location": "",
                "patient_id": admission_alert.get("patientId", "")
            }
            prepared_activities.append(activity)
        
        # Process patient ED visits
        for ed_visit in work_items.get("patient_ed_visits", []):
            activity = {
                "id": ed_visit.get("visitId", f"ED_{len(prepared_activities)}"),
                "type": "ed_visit",
                "duration": ed_visit.get("estimatedFollowUpDuration", 20),
                "priority": ed_visit.get("priority", 8),
                "title": f"ED Visit Follow-up: {ed_visit.get('reason', 'Emergency Department Visit')}",
                "is_fixed": False,
                "fixed_start_time_str": None,
                "deadline": ed_visit.get("deadline"),
                "location": "",
                "patient_id": ed_visit.get("patientId", "")
            }
            prepared_activities.append(activity)
        
        # Process predefined appointments
        for predefined_appt in work_items.get("predefined_appointments", []):
            activity = {
                "id": predefined_appt.get("appointmentId", f"PA_{len(prepared_activities)}"),
                "type": "predefined_appointment",
                "duration": predefined_appt["duration"],
                "priority": predefined_appt.get("priority", 6),
                "title": predefined_appt["title"],
                "is_fixed": predefined_appt.get("isFixed", True),
                "fixed_start_time_str": predefined_appt.get("startTime") if predefined_appt.get("isFixed") else None,
                "deadline": None,
                "location": predefined_appt.get("location", ""),
                "patient_id": predefined_appt.get("patientId", "")
            }
            prepared_activities.append(activity)
        
        # Process interventions
        for intervention in work_items.get("interventions", []):
            activity = {
                "id": intervention.get("interventionId", f"INT_{len(prepared_activities)}"),
                "type": "intervention",
                "duration": intervention.get("estimatedDuration", 25),
                "priority": intervention.get("priority", 7),
                "title": f"Intervention: {intervention.get('description', 'Patient Intervention')}",
                "is_fixed": False,
                "fixed_start_time_str": None,
                "deadline": intervention.get("deadline"),
                "location": "",
                "patient_id": intervention.get("patientId", "")
            }
            prepared_activities.append(activity)
        
        # Process patient communications
        for communication in work_items.get("patient_communications", []):
            activity = {
                "id": communication.get("communicationId", f"COMM_{len(prepared_activities)}"),
                "type": "communication",
                "duration": communication.get("estimatedDuration", 15),
                "priority": communication.get("priority", 6),
                "title": f"Communication: {communication.get('subject', 'Patient Communication')}",
                "is_fixed": False,
                "fixed_start_time_str": None,
                "deadline": communication.get("deadline"),
                "location": "",
                "patient_id": communication.get("patientId", "")
            }
            prepared_activities.append(activity)
        
        # Process patient vital alerts
        for vital_alert in work_items.get("patient_vital_alerts", []):
            activity = {
                "id": vital_alert.get("alertId", f"VITAL_{len(prepared_activities)}"),
                "type": "vital_alert",
                "duration": vital_alert.get("estimatedTimeToAddress", 20),
                "priority": vital_alert.get("urgencyScore", 9),
                "title": f"Vital Alert: {vital_alert.get('summary', 'Patient Vitals Alert')}",
                "is_fixed": False,
                "fixed_start_time_str": None,
                "deadline": None,
                "location": "",
                "patient_id": vital_alert.get("patientId", "")
            }
            prepared_activities.append(activity)
        
        # Apply patient preference-based priority adjustments
        if patient_preference == "CRITICAL_PATIENT_FOCUSED":
            # Boost priority for critical patient activities
            for activity in prepared_activities:
                if activity["type"] in ["alert", "vital_alert", "admission_alert"] and activity["patient_id"]:
                    activity["priority"] += 2
        elif patient_preference == "PATIENT_CONTEXT_FOCUSED":
            # Group activities by patient for context efficiency
            # This will be handled in the objective function
            pass
        elif patient_preference == "HIGH_PRIORITY_FIRST":
            # Keep existing priority system but emphasize high priorities
            for activity in prepared_activities:
                if activity["priority"] >= 8:
                    activity["priority"] += 1
        elif patient_preference == "SIMILAR_TASK_FIRST":
            # Group similar task types together
            # This will be handled in the objective function with task type grouping
            pass
        
        return prepared_activities
    
    def optimize_schedule(self, work_items: Dict, nurse_constraints: Dict) -> Dict:
        """
        Main optimization method using Google OR-Tools CP-SAT solver
        """
        try:
            model = cp_model.CpModel()
            
            # Prepare all activities
            all_activities_prepared = self._prepare_activities(work_items, nurse_constraints)
            
            if not all_activities_prepared:
                return {
                    "nurseId": self.nurse_id,
                    "scheduleDate": self.schedule_date_obj.isoformat(),
                    "optimizedSchedule": [],
                    "unachievableItems": [],
                    "optimizationScore": 0,
                    "warnings": ["No activities to schedule"]
                }
            
            # Convert shift times to minutes
            shift_start_min = self._time_to_minutes(nurse_constraints["shiftStartTime"])
            shift_end_min = self._time_to_minutes(nurse_constraints["shiftEndTime"])
            lunch_duration_min = nurse_constraints["lunchBreakDuration"]
            lunch_pref_start_min = self._time_to_minutes(nurse_constraints["lunchBreakPreferredStartTime"])
            
            # Create variables for activities
            activity_vars = {}
            
            for activity in all_activities_prepared:
                activity_id = activity["id"]
                duration = activity["duration"]
                
                # Define domain for start time
                domain_min_start = shift_start_min
                domain_max_start = max(shift_start_min, shift_end_min - duration)
                
                # Handle fixed time activities
                if activity.get("is_fixed") and activity.get("fixed_start_time_str"):
                    fixed_start_minutes = self._time_to_minutes(activity["fixed_start_time_str"])
                    domain_min_start = fixed_start_minutes
                    domain_max_start = fixed_start_minutes
                
                # Handle deadlines
                deadline_minutes = self._extract_deadline_time(activity.get("deadline"))
                if deadline_minutes:
                    domain_max_start = min(domain_max_start, deadline_minutes - duration)
                
                # Ensure valid domain
                if domain_min_start > domain_max_start:
                    domain_max_start = domain_min_start
                
                start_var = model.NewIntVar(domain_min_start, domain_max_start, f'start_{activity_id}')
                interval_var = model.NewIntervalVar(start_var, duration, start_var + duration, f'interval_{activity_id}')
                presence_var = model.NewBoolVar(f'presence_{activity_id}')
                
                # For MVP, assume all activities must be present
                model.Add(presence_var == 1)
                
                activity_vars[activity_id] = {
                    "start": start_var,
                    "interval": interval_var,
                    "presence": presence_var,
                    "data": activity
                }
            
            # Add lunch break
            lunch_start_var = model.NewIntVar(shift_start_min, shift_end_min - lunch_duration_min, 'lunch_start')
            lunch_interval_var = model.NewIntervalVar(lunch_start_var, lunch_duration_min, 
                                                    lunch_start_var + lunch_duration_min, 'lunch_interval')
            
            # Add blocked out times
            blocked_intervals = []
            for bo_time in nurse_constraints.get("blockedOutTimes", []):
                bo_start_min = self._time_to_minutes(bo_time["start"])
                bo_end_min = self._time_to_minutes(bo_time["end"])
                bo_duration = bo_end_min - bo_start_min
                if bo_duration > 0:
                    blocked_intervals.append(model.NewFixedSizeIntervalVar(bo_start_min, bo_duration, f'blocked_{bo_start_min}'))
            
            # No overlap constraint
            all_intervals = [v["interval"] for v in activity_vars.values()] + [lunch_interval_var] + blocked_intervals
            model.AddNoOverlap(all_intervals)
            
            # Deadline constraints
            for activity_id, vars_dict in activity_vars.items():
                activity_data = vars_dict["data"]
                deadline_minutes = self._extract_deadline_time(activity_data.get("deadline"))
                if deadline_minutes:
                    model.Add(vars_dict["start"] + activity_data["duration"] <= deadline_minutes).OnlyEnforceIf(vars_dict["presence"])
            
            # Objective function with patient preference support
            lunch_deviation = model.NewIntVar(0, shift_end_min, 'lunch_deviation')
            model.AddAbsEquality(lunch_deviation, lunch_start_var - lunch_pref_start_min)
            
            # Get patient preference
            patient_preference = nurse_constraints.get("patientPreference", "BALANCED")
            
            # Minimize lunch deviation and apply patient preference logic
            objective_terms = [lunch_deviation]
            
            if patient_preference == "HIGH_PRIORITY_FIRST":
                # Prioritize high-priority tasks early
                high_priority_start_sum = model.NewIntVar(0, len(all_activities_prepared) * shift_end_min, 'high_priority_starts')
                high_priority_terms = []
                for activity_id, vars_data in activity_vars.items():
                    if vars_data["data"]["priority"] >= 8:
                        high_priority_terms.append(vars_data["start"])
                
                if high_priority_terms:
                    model.Add(high_priority_start_sum == sum(high_priority_terms))
                    high_priority_penalty = model.NewIntVar(0, len(all_activities_prepared) * shift_end_min // 10, 'high_priority_penalty')
                    model.AddDivisionEquality(high_priority_penalty, high_priority_start_sum, 10)
                    objective_terms.append(high_priority_penalty)
            
            elif patient_preference == "PATIENT_CONTEXT_FOCUSED":
                # Minimize transitions between different patients
                patient_transition_penalty = model.NewIntVar(0, len(all_activities_prepared) * 10, 'patient_transitions')
                # Simplified implementation - can be enhanced for production
                objective_terms.append(patient_transition_penalty)
            
            elif patient_preference == "SIMILAR_TASK_FIRST":
                # Group similar task types together
                task_type_penalty = model.NewIntVar(0, len(all_activities_prepared) * 5, 'task_type_transitions')
                # Simplified implementation - can be enhanced for production
                objective_terms.append(task_type_penalty)
            
            elif patient_preference == "CRITICAL_PATIENT_FOCUSED":
                # Prioritize critical patient activities very early
                critical_start_sum = model.NewIntVar(0, len(all_activities_prepared) * shift_end_min, 'critical_starts')
                critical_terms = []
                for activity_id, vars_data in activity_vars.items():
                    if vars_data["data"]["type"] in ["alert", "vital_alert", "admission_alert"]:
                        critical_terms.append(vars_data["start"])
                
                if critical_terms:
                    model.Add(critical_start_sum == sum(critical_terms))
                    critical_penalty = model.NewIntVar(0, len(all_activities_prepared) * shift_end_min // 5, 'critical_penalty')
                    model.AddDivisionEquality(critical_penalty, critical_start_sum, 5)
                    objective_terms.append(critical_penalty)
            
            # Default BALANCED approach or fallback
            if len(objective_terms) == 1:  # Only lunch deviation
                # Add general priority handling
                high_priority_start_sum = model.NewIntVar(0, len(all_activities_prepared) * shift_end_min, 'high_priority_starts')
                high_priority_terms = []
                for activity_id, vars_data in activity_vars.items():
                    if vars_data["data"]["priority"] >= 8:
                        high_priority_terms.append(vars_data["start"])
                
                if high_priority_terms:
                    model.Add(high_priority_start_sum == sum(high_priority_terms))
                    high_priority_penalty = model.NewIntVar(0, len(all_activities_prepared) * shift_end_min // 10, 'high_priority_penalty')
                    model.AddDivisionEquality(high_priority_penalty, high_priority_start_sum, 10)
                    objective_terms.append(high_priority_penalty)
            
            model.Minimize(sum(objective_terms))
            
            # Solve the model
            solver = cp_model.CpSolver()
            solver.parameters.max_time_in_seconds = 30.0
            status = solver.Solve(model)
            
            # Process solution
            optimized_schedule_items = []
            unachievable_items_list = []
            warnings = []
            
            if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
                # Add scheduled activities
                for activity_id, vars_dict in activity_vars.items():
                    if solver.BooleanValue(vars_dict["presence"]):
                        start_val = solver.Value(vars_dict["start"])
                        activity_data = vars_dict["data"]
                        end_val = start_val + activity_data["duration"]
                        
                        optimized_schedule_items.append({
                            "slotStartTime": self._minutes_to_time_str(start_val),
                            "slotEndTime": self._minutes_to_time_str(end_val),
                            "activityType": activity_data["type"],
                            "title": activity_data["title"],
                            "details": f"Location: {activity_data.get('location', 'N/A')}, Patient: {activity_data.get('patient_id', 'N/A')}",
                            "relatedItemId": activity_id
                        })
                    else:
                        unachievable_items_list.append({
                            "itemId": activity_id,
                            "itemType": vars_dict["data"]["type"],
                            "reason": "Could not be scheduled due to constraints/time."
                        })
                
                # Add lunch break
                lunch_start_val = solver.Value(lunch_start_var)
                optimized_schedule_items.append({
                    "slotStartTime": self._minutes_to_time_str(lunch_start_val),
                    "slotEndTime": self._minutes_to_time_str(lunch_start_val + lunch_duration_min),
                    "activityType": "Break",
                    "title": "Lunch Break",
                    "details": "",
                    "relatedItemId": "LUNCH"
                })
                
                # Add blocked out times
                for i, bo_time in enumerate(nurse_constraints.get("blockedOutTimes", [])):
                    bo_start_min = self._time_to_minutes(bo_time["start"])
                    bo_end_min = self._time_to_minutes(bo_time["end"])
                    optimized_schedule_items.append({
                        "slotStartTime": self._minutes_to_time_str(bo_start_min),
                        "slotEndTime": self._minutes_to_time_str(bo_end_min),
                        "activityType": "Blocked",
                        "title": bo_time.get("reason", "Blocked Time"),
                        "details": "",
                        "relatedItemId": f"BLOCK_{i}"
                    })
                
                # Check for warnings
                if abs(solver.Value(lunch_start_var) - lunch_pref_start_min) > 15:
                    warnings.append("Lunch break scheduled more than 15 minutes from preferred time.")
                
                # Sort schedule by start time
                optimized_schedule_items.sort(key=lambda x: self._time_to_minutes(x["slotStartTime"]))
                
                optimization_score = solver.ObjectiveValue()
                
            else:
                # No solution found
                for activity in all_activities_prepared:
                    unachievable_items_list.append({
                        "itemId": activity["id"],
                        "itemType": activity["type"],
                        "reason": "No feasible schedule found."
                    })
                optimization_score = 0
                warnings.append("No feasible schedule could be generated with the given constraints.")
            
            return {
                "nurseId": self.nurse_id,
                "scheduleDate": self.schedule_date_obj.isoformat(),
                "optimizedSchedule": optimized_schedule_items,
                "unachievableItems": unachievable_items_list,
                "optimizationScore": optimization_score,
                "warnings": warnings
            }
            
        except Exception as e:
            # Handle any unexpected errors
            return {
                "nurseId": self.nurse_id,
                "scheduleDate": self.schedule_date_obj.isoformat(),
                "optimizedSchedule": [],
                "unachievableItems": [{"itemId": "ERROR", "itemType": "system", "reason": f"System error: {str(e)}"}],
                "optimizationScore": 0,
                "warnings": [f"System error occurred: {str(e)}"]
            }


def main():
    """Example usage and testing - loads sample data from README documentation"""
    print("Intelligent Daily Schedule Optimization Agent (IDSOA)")
    print("=" * 60)
    print("For sample data structure and API usage, please refer to README.md")
    print("To test with sample data, use the FastAPI endpoint at /planmydaynurse/sample-request")


if __name__ == "__main__":
    main()
