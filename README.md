
# Intelligent Daily Schedule Optimization Agent (IDSOA)

An AI-powered schedule optimization system designed specifically for healthcare professionals (nurses) to optimize their daily work schedules using Google OR-Tools constraint programming.

## Overview

The IDSOA takes a nurse's daily work items (appointments, tasks, alerts, follow-ups) and constraints (shift times, blocked periods, preferences) and generates an optimized, time-blocked schedule that maximizes efficiency while respecting all constraints.

## Features

- **Constraint-based Optimization**: Uses Google OR-Tools CP-SAT solver for robust scheduling
- **Multiple Activity Types**: Handles appointments, meetings, tasks, critical alerts, and follow-ups
- **Flexible Constraints**: Supports fixed-time activities, deadlines, blocked periods, and lunch breaks
- **Priority-based Scheduling**: Prioritizes high-importance activities and schedules them optimally
- **Comprehensive Output**: Returns structured JSON with optimized schedule, unachievable items, and warnings

## Installation

1. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Verify Installation**:
   ```bash
   python -c "from ortools.sat.python import cp_model; print('OR-Tools installed successfully')"
   ```

## API Endpoints

### FastAPI Server

Start the API server:
```bash
python api.py
```

The API will be available at:
- **Main endpoint**: `POST /planmydaynurse/optimize`
- **Sample data**: `GET /planmydaynurse/sample-request`
- **Health check**: `GET /health`

### Sample JSON Request

Here's a complete sample request that you can use to test the API:

```json
{
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
                "isFixedTime": true,
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
                "isFixedTime": true,
                "initialPriorityScore": 5
            }
        ],
        "tasks": [
            {
                "taskId": "T501",
                "patientId": "102",
                "description": "Call Jane Smith re: BG monitoring",
                "estimatedDuration": 25,
                "initialPriorityScore": 9,
                "deadline": "12:00:00",
                "locationDependency": "Desk"
            }
        ],
        "critical_alerts_to_address": [],
        "break_times": [
            {
                "breakId": "BREAK001",
                "duration": 15,
                "isFixed": true,
                "startTime": "12:00:00"
            }
        ],
        "care_plans": [
            {
                "carePlanId": "CP001",
                "patientId": "102",
                "description": "Diabetes Management Plan",
                "estimatedDuration": 30,
                "priority": 8,
                "deadline": "None"
            }
        ],
        "patient_vital_alerts": [
            {
                "alertId": "VA001",
                "patientId": "102",
                "summary": "High Blood Pressure Alert",
                "estimatedTimeToAddress": 20,
                "urgencyScore": 10
            }
        ],
        "interventions": [
            {
                "interventionId": "INT001",
                "patientId": "102",
                "description": "Schedule follow-up visit",
                "estimatedDuration": 25,
                "priority": 7,
                "deadline": "None"
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
        ],
        "patientPreference": "BALANCED"
    }
}
```

## Usage

### Basic Usage

```python
from schedule_optimizer import IntelligentDailyScheduleOptimizer, MockKBS

# Initialize the optimizer
kbs = MockKBS()
optimizer = IntelligentDailyScheduleOptimizer(
    nurse_id="NURSE001",
    schedule_date="2023-10-01",
    knowledge_base_accessor=kbs
)

# Define work items
work_items = {
    "appointments": [
        {
            "itemId": "APPT001",
            "title": "Patient Consultation",
            "startTime": "09:00:00",
            "estimatedDuration": 30,
            "isFixedTime": True,
            "initialPriorityScore": 8
        }
    ],
    "tasks": [
        {
            "taskId": "TASK001",
            "description": "Chart Review",
            "estimatedDuration": 20,
            "initialPriorityScore": 6,
            "deadline": "12:00:00"
        }
    ],
    "critical_alerts_to_address": [],
    "calendar_events": [],
    "follow_ups": []
}

# Define constraints
nurse_constraints = {
    "shiftStartTime": "08:00:00",
    "shiftEndTime": "17:00:00",
    "lunchBreakPreferredStartTime": "12:30:00",
    "lunchBreakDuration": 30,
    "blockedOutTimes": []
}

# Optimize schedule
result = optimizer.optimize_schedule(work_items, nurse_constraints)
print(json.dumps(result, indent=2))
```

### Running the Example

To run the built-in example with sample data:

```bash
python schedule_optimizer.py
```

This will demonstrate the optimizer with realistic nursing schedule data including:
- Fixed-time appointments
- Flexible tasks with deadlines
- Critical alerts requiring immediate attention
- Mandatory training blocks
- Lunch break scheduling

## Input Data Structure

### Work Items

The `work_items` dictionary supports five types of activities:

#### Appointments
```python
{
    "itemId": "V701",
    "itemType": "Appointment",
    "patientId": "102",
    "title": "Jane Smith - Diabetes FU",
    "startTime": "09:00:00",          # Required for fixed-time
    "estimatedDuration": 45,          # minutes
    "location": "Clinic A",
    "isFixedTime": True,              # Cannot be moved
    "initialPriorityScore": 7
}
```

#### Tasks
```python
{
    "taskId": "T501",
    "patientId": "102",
    "description": "Call Jane Smith re: BG monitoring",
    "estimatedDuration": 25,
    "initialPriorityScore": 9,
    "deadline": "17:00:00",           # Optional deadline
    "locationDependency": "Desk"
}
```

#### Critical Alerts
```python
{
    "alertId": "ALERT790",
    "patientId": "102",
    "alertType": "Critical Lab",
    "summary": "K+ 2.8 (Low Potassium)",
    "estimatedTimeToAddress": 20,
    "urgencyScore": 10                # High urgency = high priority
}
```

#### Calendar Events
```python
{
    "itemId": "EVT001",
    "itemType": "Meeting",
    "title": "Team Huddle",
    "startTime": "10:00:00",
    "estimatedDuration": 60,
    "isFixedTime": True,
    "initialPriorityScore": 4
}
```

#### Follow-ups
```python
{
    "followUpId": "FU001",
    "patientId": "205",
    "reason": "Post-Discharge Call",
    "estimatedDurationForFollowUpAction": 15,
    "initialPriorityScore": 7
}
```

### Nurse Constraints

```python
{
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
    ],
    "travelMatrix": {                 # Optional travel times
        ("Clinic A", "Clinic B"): 15
    },
    "currentLocation": "Clinic A"     # Optional starting location
}
```

## Output Structure

The optimizer returns a comprehensive JSON structure:

```python
{
    "nurseId": "NURSE001",
    "scheduleDate": "2023-10-01",
    "optimizedSchedule": [
        {
            "slotStartTime": "08:00:00",
            "slotEndTime": "08:20:00",
            "activityType": "alert",
            "title": "Alert: K+ 2.8 (Low Potassium)",
            "details": "Location: , Patient: 102",
            "relatedItemId": "ALERT790"
        }
        # ... more scheduled items
    ],
    "unachievableItems": [
        {
            "itemId": "TASK999",
            "itemType": "task",
            "reason": "Could not be scheduled due to constraints/time."
        }
    ],
    "optimizationScore": 1250.0,
    "warnings": [
        "Lunch break scheduled more than 15 minutes from preferred time."
    ]
}
```

## Optimization Algorithm

The system uses Google OR-Tools CP-SAT (Constraint Programming - Satisfiability) solver with the following approach:

1. **Data Preprocessing**: Converts all times to minutes from midnight for easier calculation
2. **Variable Creation**: Creates start time, duration, and presence variables for each activity
3. **Constraint Application**:
   - No overlap between activities
   - Respect fixed start times
   - Honor deadlines
   - Stay within shift boundaries
   - Accommodate blocked periods
4. **Objective Optimization**:
   - Minimize lunch break deviation from preferred time
   - Prioritize early scheduling of high-priority activities
   - Maximize total priority score of scheduled items

## Configuration

### Mock Knowledge Base System

The `MockKBS` class provides default rules and constraints:

```python
{
    "task_default_duration": 30,     # Default task duration (minutes)
    "alert_default_address_time": 15, # Default alert handling time
    "priority_weights": {             # Text to numeric priority mapping
        "High": 10,
        "Medium": 5,
        "Low": 1
    }
}
```

### Solver Parameters

- **Time Limit**: 30 seconds (configurable)
- **Optimization Mode**: Minimize weighted objective function
- **Solution Quality**: Accepts both optimal and feasible solutions

## Troubleshooting

### Common Issues

1. **No Feasible Solution**:
   - Check for conflicting fixed-time appointments
   - Verify total work exceeds shift duration
   - Review deadline constraints

2. **Import Errors**:
   ```bash
   pip install --upgrade ortools
   ```

3. **Time Format Errors**:
   - Use "HH:MM:SS" format for all times
   - Ensure times are within 24-hour format

### Debug Mode

Enable detailed logging by modifying the solver parameters:

```python
solver = cp_model.CpSolver()
solver.parameters.max_time_in_seconds = 30.0
solver.parameters.log_search_progress = True  # Enable logging
```

## Advanced Features

### Travel Time Support

When `travelMatrix` is provided, the system can account for travel time between locations:

```python
nurse_constraints = {
    # ... other constraints
    "travelMatrix": {
        ("Clinic A", "Clinic B"): 15,  # 15 minutes travel time
        ("Clinic B", "Clinic A"): 15,
        ("Clinic A", "Desk"): 5,
        ("Desk", "Clinic A"): 5
    },
    "currentLocation": "Clinic A"
}
```

### Priority Scoring

Activities are prioritized using:
- Numerical priority scores (1-10)
- Urgency scores for alerts
- Text-based priorities ("High", "Medium", "Low")

### Deadline Handling

The system supports flexible deadline formats:
- Time only: "17:00:00"
- Full datetime: "2023-10-01T17:00:00"

## Performance

- **Typical solve time**: < 5 seconds for daily schedules
- **Maximum activities**: Tested with 50+ activities
- **Memory usage**: Minimal (< 100MB)

## Contributing

This is a demonstration implementation. For production use, consider:
- Enhanced error handling
- Database integration for knowledge base
- Web API interface
- Real-time schedule updates
- Multi-day optimization

## License

This project is provided as-is for educational and demonstration purposes.
