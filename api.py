
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Dict, List, Optional
from schedule_optimizer import IntelligentDailyScheduleOptimizer, MockKBS
import uvicorn

app = FastAPI(title="PlanMyDayNurse - Intelligent Schedule Optimization API", version="1.0.0")

# Pydantic models for request/response validation
class Appointment(BaseModel):
    itemId: str
    itemType: str = "Appointment"
    patientId: Optional[str] = ""
    title: str
    startTime: Optional[str] = None
    estimatedDuration: int
    location: Optional[str] = ""
    isFixedTime: bool = False
    initialPriorityScore: int = 5

class CalendarEvent(BaseModel):
    itemId: str
    itemType: str = "Meeting"
    title: str
    startTime: Optional[str] = None
    estimatedDuration: int
    location: Optional[str] = ""
    isFixedTime: bool = False
    initialPriorityScore: int = 4

class Task(BaseModel):
    taskId: str
    patientId: Optional[str] = ""
    description: str
    estimatedDuration: int
    initialPriorityScore: int = 5
    dueDate: Optional[str] = None
    deadline: Optional[str] = None
    locationDependency: Optional[str] = ""

class CriticalAlert(BaseModel):
    alertId: str
    patientId: Optional[str] = ""
    alertType: str
    summary: str
    estimatedTimeToAddress: int
    urgencyScore: int = 10

class FollowUp(BaseModel):
    followUpId: str
    patientId: Optional[str] = ""
    reason: str
    estimatedDurationForFollowUpAction: int
    initialPriorityScore: int = 7

class BlockedTime(BaseModel):
    start: str
    end: str
    reason: str = ""

# Additional constraint models for comprehensive patient care
class BreakTime(BaseModel):
    breakId: Optional[str] = None
    startTime: Optional[str] = None
    duration: int
    reason: str = ""
    isFixed: bool = False

class CarePlan(BaseModel):
    carePlanId: Optional[str] = None
    patientId: str
    description: str
    estimatedDuration: int = 30
    priority: int = 8
    deadline: Optional[str] = None

class PatientAdmissionAlert(BaseModel):
    alertId: Optional[str] = None
    patientId: str
    summary: str
    estimatedTimeToAddress: int = 15
    urgencyScore: int = 9

class PatientEDVisit(BaseModel):
    visitId: Optional[str] = None
    patientId: str
    reason: str
    estimatedFollowUpDuration: int = 20
    priority: int = 8
    deadline: Optional[str] = None

class PredefinedAppointment(BaseModel):
    appointmentId: Optional[str] = None
    patientId: Optional[str] = ""
    title: str
    startTime: Optional[str] = None
    duration: int
    priority: int = 6
    location: Optional[str] = ""
    isFixed: bool = True

class Intervention(BaseModel):
    interventionId: Optional[str] = None
    patientId: str
    description: str
    estimatedDuration: int = 25
    priority: int = 7
    deadline: Optional[str] = None

class PatientCommunication(BaseModel):
    communicationId: Optional[str] = None
    patientId: str
    subject: str
    estimatedDuration: int = 15
    priority: int = 6
    deadline: Optional[str] = None

class PatientVitalAlert(BaseModel):
    alertId: Optional[str] = None
    patientId: str
    summary: str
    estimatedTimeToAddress: int = 20
    urgencyScore: int = 9

class WorkItems(BaseModel):
    appointments: List[Appointment] = []
    calendar_events: List[CalendarEvent] = []
    tasks: List[Task] = []
    critical_alerts_to_address: List[CriticalAlert] = []
    follow_ups: List[FollowUp] = []
    break_times: List[BreakTime] = []
    care_plans: List[CarePlan] = []
    patient_admission_alerts: List[PatientAdmissionAlert] = []
    patient_ed_visits: List[PatientEDVisit] = []
    predefined_appointments: List[PredefinedAppointment] = []
    interventions: List[Intervention] = []
    patient_communications: List[PatientCommunication] = []
    patient_vital_alerts: List[PatientVitalAlert] = []

class NurseConstraints(BaseModel):
    shiftStartTime: str
    shiftEndTime: str
    lunchBreakPreferredStartTime: str
    lunchBreakDuration: int
    blockedOutTimes: List[BlockedTime] = []
    patientPreference: str = "BALANCED"  # CRITICAL_PATIENT_FOCUSED, BALANCED, HIGH_PRIORITY_FIRST, SIMILAR_TASK_FIRST, PATIENT_CONTEXT_FOCUSED

class ScheduleOptimizationRequest(BaseModel):
    nurseId: str
    scheduleDate: str
    workItems: WorkItems
    nurseConstraints: NurseConstraints

class ScheduleItem(BaseModel):
    slotStartTime: str
    slotEndTime: str
    activityType: str
    title: str
    details: str
    relatedItemId: str

class UnachievableItem(BaseModel):
    itemId: str
    itemType: str
    reason: str

class ScheduleOptimizationResponse(BaseModel):
    nurseId: str
    scheduleDate: str
    optimizedSchedule: List[ScheduleItem]
    unachievableItems: List[UnachievableItem]
    optimizationScore: float
    warnings: List[str]

@app.get("/")
async def root():
    return {"message": "PlanMyDayNurse - Intelligent Schedule Optimization API", "status": "running"}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "schedule-optimizer"}

@app.post("/planmydaynurse/optimize", response_model=ScheduleOptimizationResponse)
async def optimize_schedule(request: ScheduleOptimizationRequest):
    """
    Optimize a nurse's daily schedule based on work items and constraints.
    """
    try:
        # Initialize the optimizer
        mock_kbs = MockKBS()
        optimizer = IntelligentDailyScheduleOptimizer(
            nurse_id=request.nurseId,
            schedule_date=request.scheduleDate,
            knowledge_base_accessor=mock_kbs
        )
        
        # Convert Pydantic models to dictionaries
        work_items_dict = request.workItems.dict()
        nurse_constraints_dict = request.nurseConstraints.dict()
        
        # Run optimization
        result = optimizer.optimize_schedule(work_items_dict, nurse_constraints_dict)
        
        return ScheduleOptimizationResponse(**result)
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Optimization failed: {str(e)}")

@app.get("/planmydaynurse/sample-request")
async def get_sample_request():
    """
    Returns a sample request format for testing the optimization endpoint.
    """
    sample_request = {
        "nurseId": "NBetty01",
        "scheduleDate": "2023-10-01",
        "workItems": {
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
        },
        "nurseConstraints": {
            "shiftStartTime": "08:00:00",
            "shiftEndTime": "17:00:00",
            "lunchBreakPreferredStartTime": "12:30:00",
            "lunchBreakDuration": 30,
            "blockedOutTimes": [
                {
                    "start": "13:00:00",
                    "end": "13:30:00",
                    "reason": "Mandatory Training"
                }
            ]
        }
    }
    
    return sample_request

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=5000)
