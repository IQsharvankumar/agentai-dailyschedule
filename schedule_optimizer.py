
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
        Combine all work items into a unified list with consistent attributes for the solver
        """
        prepared_activities = []
        
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
            
            # Objective function
            lunch_deviation = model.NewIntVar(0, shift_end_min, 'lunch_deviation')
            model.AddAbsEquality(lunch_deviation, lunch_start_var - lunch_pref_start_min)
            
            # Minimize lunch deviation and prioritize high-priority tasks early
            high_priority_start_sum = model.NewIntVar(0, len(all_activities_prepared) * shift_end_min, 'high_priority_starts')
            high_priority_terms = []
            for activity_id, vars_data in activity_vars.items():
                if vars_data["data"]["priority"] >= 8:
                    high_priority_terms.append(vars_data["start"])
            
            if high_priority_terms:
                model.Add(high_priority_start_sum == sum(high_priority_terms))
                # Create a variable for the division result
                high_priority_penalty = model.NewIntVar(0, len(all_activities_prepared) * shift_end_min // 10, 'high_priority_penalty')
                model.AddDivisionEquality(high_priority_penalty, high_priority_start_sum, 10)
                model.Minimize(lunch_deviation + high_priority_penalty)
            else:
                model.Minimize(lunch_deviation)
            
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
    """Example usage and testing"""
    print("Intelligent Daily Schedule Optimization Agent (IDSOA)")
    print("=" * 60)
    
    # Initialize components
    mock_kbs = MockKBS()
    optimizer = IntelligentDailyScheduleOptimizer(
        nurse_id="NBetty01", 
        schedule_date="2023-10-01", 
        knowledge_base_accessor=mock_kbs
    )
    
    # Sample work items
    sample_work_items = {
        "appointments": [
            {
                "itemId": "V701",
                "itemType": "Appointment",
                "patientId": "102",
                "title": "Jane Smith - Diabetes FU",
                "startTime": "09:00:00",
                "estimatedDuration": 45,
                "location": "Clinic A",
                "isFixedTime": True,
                "initialPriorityScore": 7
            },
            {
                "itemId": "V702",
                "itemType": "Appointment",
                "patientId": "P002",
                "title": "Robert Blue - Checkup",
                "startTime": "14:00:00",
                "estimatedDuration": 30,
                "location": "Clinic B",
                "isFixedTime": True,
                "initialPriorityScore": 5
            }
        ],
        "calendar_events": [
            {
                "itemId": "EVT001",
                "itemType": "Meeting",
                "title": "Team Huddle",
                "startTime": "10:00:00",
                "estimatedDuration": 60,
                "location": "Conf Room B",
                "isFixedTime": True,
                "initialPriorityScore": 4
            }
        ],
        "tasks": [
            {
                "taskId": "T501",
                "patientId": "102",
                "description": "Call Jane Smith re: BG monitoring",
                "estimatedDuration": 25,
                "initialPriorityScore": 9,
                "dueDate": "2023-10-01",
                "deadline": "17:00:00",
                "locationDependency": "Desk"
            },
            {
                "taskId": "T502",
                "patientId": "P003",
                "description": "Prep P003 chart for tomorrow",
                "estimatedDuration": 15,
                "initialPriorityScore": 6,
                "dueDate": "2023-10-01",
                "deadline": "16:00:00",
                "locationDependency": "Desk"
            }
        ],
        "critical_alerts_to_address": [
            {
                "alertId": "ALERT790",
                "patientId": "102",
                "alertType": "Critical Lab",
                "summary": "K+ 2.8 (Low Potassium)",
                "estimatedTimeToAddress": 20,
                "urgencyScore": 10
            }
        ],
        "follow_ups": [
            {
                "followUpId": "FU001",
                "patientId": "205",
                "reason": "Post-Discharge Call",
                "estimatedDurationForFollowUpAction": 15,
                "initialPriorityScore": 7
            }
        ]
    }
    
    # Sample nurse constraints
    sample_nurse_constraints = {
        "shiftStartTime": "08:00:00",
        "shiftEndTime": "17:00:00",
        "lunchBreakPreferredStartTime": "12:30:00",
        "lunchBreakDuration": 30,
        "blockedOutTimes": [
            {"start": "13:00:00", "end": "13:30:00", "reason": "Mandatory Training"}
        ]
    }
    
    # Run optimization
    print("Running schedule optimization...")
    optimized_schedule = optimizer.optimize_schedule(sample_work_items, sample_nurse_constraints)
    
    # Display results
    print("\n--- Optimized Schedule Results ---")
    print(json.dumps(optimized_schedule, indent=2))
    
    print("\n--- Schedule Summary ---")
    print(f"Nurse ID: {optimized_schedule['nurseId']}")
    print(f"Schedule Date: {optimized_schedule['scheduleDate']}")
    print(f"Optimization Score: {optimized_schedule['optimizationScore']}")
    print(f"Total Scheduled Items: {len(optimized_schedule['optimizedSchedule'])}")
    print(f"Unachievable Items: {len(optimized_schedule['unachievableItems'])}")
    
    if optimized_schedule['warnings']:
        print("\nWarnings:")
        for warning in optimized_schedule['warnings']:
            print(f"  - {warning}")
    
    print("\nScheduled Activities:")
    for item in optimized_schedule['optimizedSchedule']:
        print(f"  {item['slotStartTime']} - {item['slotEndTime']}: {item['title']} ({item['activityType']})")


if __name__ == "__main__":
    main()
