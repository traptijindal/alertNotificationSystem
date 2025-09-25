from fastapi import FastAPI, HTTPException, Body, Query
from pydantic import BaseModel, Field
from enum import Enum
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta, time, timezone, date
import uuid

app = FastAPI(title="Alerting & Notification Platform (MVP)")


class Severity(str, Enum):
    INFO = "Info"
    WARNING = "Warning"
    CRITICAL = "Critical"

class DeliveryType(str, Enum):
    IN_APP = "in_app"
    EMAIL = "email"
    SMS = "sms"

class VisibilityType(str, Enum):
    ORGANIZATION = "organization"
    TEAM = "team"
    USER = "user"


DB = {
    "teams": {},    
    "users": {},   
    "alerts": {},   
    "deliveries": [],  
    "user_alert_prefs": {}, 
}



def now_utc() -> datetime:
    return datetime.now(timezone.utc)

def today_utc_date() -> date:
    return now_utc().date()


class Team(BaseModel):
    id: str
    name: str

class User(BaseModel):
    id: str
    name: str
    team_id: Optional[str]
   

class Alert(BaseModel):
    id: str
    title: str
    message: str
    severity: Severity = Severity.INFO
    delivery_type: DeliveryType = DeliveryType.IN_APP
    visibility: VisibilityType = VisibilityType.ORGANIZATION
    visibility_ids: Optional[List[str]] = None  
    start_time: datetime = Field(default_factory=now_utc)
    expiry_time: Optional[datetime] = None
    reminder_enabled: bool = True
    reminder_frequency_minutes: int = 120 
    archived: bool = False
    created_at: datetime = Field(default_factory=now_utc)

    def is_active(self, at: Optional[datetime] = None) -> bool:
        if at is None:
            at = now_utc()
        if self.archived:
            return False
        if self.start_time and at < self.start_time:
            return False
        if self.expiry_time and at >= self.expiry_time:
            return False
        return True

class NotificationDelivery(BaseModel):
    id: str
    alert_id: str
    user_id: str
    delivered_at: datetime
    channel: DeliveryType


class UserAlertState:
    def mark_read(self, pref: "UserAlertPreference"):
        raise NotImplementedError()
    def mark_unread(self, pref: "UserAlertPreference"):
        raise NotImplementedError()
    def snooze(self, pref: "UserAlertPreference", until: datetime):
        raise NotImplementedError()

class ReadState(UserAlertState):
    def mark_read(self, pref: "UserAlertPreference"):
     
        return
    def mark_unread(self, pref: "UserAlertPreference"):
        pref.state = UnreadState()
        pref.last_read_at = None
    def snooze(self, pref: "UserAlertPreference", until: datetime):
        pref.state = SnoozedState()
        pref.snoozed_until = until

class UnreadState(UserAlertState):
    def mark_read(self, pref: "UserAlertPreference"):
        pref.state = ReadState()
        pref.last_read_at = now_utc()
    def mark_unread(self, pref: "UserAlertPreference"):
        return
    def snooze(self, pref: "UserAlertPreference", until: datetime):
        pref.state = SnoozedState()
        pref.snoozed_until = until

class SnoozedState(UserAlertState):
    def mark_read(self, pref: "UserAlertPreference"):
        pref.state = ReadState()
        pref.last_read_at = now_utc()
        pref.snoozed_until = None
    def mark_unread(self, pref: "UserAlertPreference"):
        pref.state = UnreadState()
        pref.snoozed_until = None
    def snooze(self, pref: "UserAlertPreference", until: datetime):
        pref.snoozed_until = until

class UserAlertPreference(BaseModel):
    user_id: str
    alert_id: str
    state: UserAlertState  
    last_read_at: Optional[datetime] = None
    snoozed_until: Optional[datetime] = None

  
    model_config = {
        "arbitrary_types_allowed": True
    }

    def mark_read(self):
        self.state.mark_read(self)

    def mark_unread(self):
        self.state.mark_unread(self)

    def snooze_for_today(self):
        end_of_today = datetime.combine(today_utc_date() + timedelta(days=1), time(0, 0), tzinfo=timezone.utc)
        self.state.snooze(self, end_of_today)

    def is_snoozed_now(self) -> bool:
        if not self.snoozed_until:
            return False
        return now_utc() < self.snoozed_until

    def ensure_snooze_expired(self):
        if isinstance(self.state, SnoozedState) and (not self.snoozed_until or now_utc() >= self.snoozed_until):
            self.state = UnreadState()
            self.snoozed_until = None



class TeamManager:
    @staticmethod
    def add_team(name: str) -> Team:
        team_id = str(uuid.uuid4())
        t = Team(id=team_id, name=name)
        DB["teams"][team_id] = t
        return t

    @staticmethod
    def get_team(team_id: str) -> Team:
        return DB["teams"].get(team_id)

    @staticmethod
    def list_teams() -> List[Team]:
        return list(DB["teams"].values())

class UserManager:
    @staticmethod
    def add_user(name: str, team_id: Optional[str] = None) -> User:
        user_id = str(uuid.uuid4())
        u = User(id=user_id, name=name, team_id=team_id)
        DB["users"][user_id] = u
        return u

    @staticmethod
    def get_user(user_id: str) -> Optional[User]:
        return DB["users"].get(user_id)

    @staticmethod
    def list_users() -> List[User]:
        return list(DB["users"].values())

class AlertManager:
    @staticmethod
    def create_alert(title: str, message: str, severity: Severity, delivery_type: DeliveryType,
                     visibility: VisibilityType, visibility_ids: Optional[List[str]] = None,
                     start_time: Optional[datetime] = None, expiry_time: Optional[datetime] = None,
                     reminder_enabled: bool = True, reminder_frequency_minutes: int = 120) -> Alert:
        alert_id = str(uuid.uuid4())
        if not start_time:
            start_time = now_utc()
        a = Alert(
            id=alert_id,
            title=title,
            message=message,
            severity=severity,
            delivery_type=delivery_type,
            visibility=visibility,
            visibility_ids=visibility_ids,
            start_time=start_time,
            expiry_time=expiry_time,
            reminder_enabled=reminder_enabled,
            reminder_frequency_minutes=reminder_frequency_minutes,
        )
        DB["alerts"][alert_id] = a

        AudienceRegistrar.register_audience(a)
        return a

    @staticmethod
    def update_alert(alert_id: str, **kwargs) -> Alert:
        a = DB["alerts"].get(alert_id)
        if not a:
            raise KeyError("Alert not found")
        for k, v in kwargs.items():
            if hasattr(a, k) and v is not None:
                setattr(a, k, v)

        if "visibility" in kwargs or "visibility_ids" in kwargs:
            AudienceRegistrar.register_audience(a)
        return a

    @staticmethod
    def list_alerts(severity: Optional[Severity] = None, active_only: Optional[bool] = None,
                    audience_filter: Optional[VisibilityType] = None) -> List[Alert]:
        result = list(DB["alerts"].values())
        if severity:
            result = [a for a in result if a.severity == severity]
        if active_only is True:
            result = [a for a in result if a.is_active()]
        elif active_only is False:
            result = [a for a in result if not a.is_active()]
        if audience_filter:
            result = [a for a in result if a.visibility == audience_filter]
        return result


class AudienceRegistrar:
    @staticmethod
    def resolve_audience(alert: Alert) -> List[str]:
       
        if alert.visibility == VisibilityType.ORGANIZATION:
            return [u.id for u in UserManager.list_users()]
        elif alert.visibility == VisibilityType.TEAM:
           
            if not alert.visibility_ids:
                return []
            teams = set(alert.visibility_ids)
            return [u.id for u in UserManager.list_users() if u.team_id in teams]
        elif alert.visibility == VisibilityType.USER:
            if not alert.visibility_ids:
                return []
            return [uid for uid in alert.visibility_ids if uid in DB["users"]]
        return []

    @staticmethod
    def register_audience(alert: Alert):
        user_ids = AudienceRegistrar.resolve_audience(alert)
        for uid in user_ids:
            key = (uid, alert.id)
            if key not in DB["user_alert_prefs"]:
                pref = UserAlertPreference(user_id=uid, alert_id=alert.id, state=UnreadState())
                DB["user_alert_prefs"][key] = pref


class DeliveryStrategy:
    def deliver(self, alert: Alert, user: User) -> NotificationDelivery:
        raise NotImplementedError()

class InAppDelivery(DeliveryStrategy):
    def deliver(self, alert: Alert, user: User) -> NotificationDelivery:
       
        delivery = NotificationDelivery(id=str(uuid.uuid4()), alert_id=alert.id, user_id=user.id,
                                        delivered_at=now_utc(), channel=DeliveryType.IN_APP)
        DB["deliveries"].append(delivery)
       
        key = (user.id, alert.id)
        pref = DB["user_alert_prefs"].get(key)
        if not pref:
            pref = UserAlertPreference(user_id=user.id, alert_id=alert.id, state=UnreadState())
            DB["user_alert_prefs"][key] = pref
      
        pref.ensure_snooze_expired()
        if not pref.is_snoozed_now():
          
            if not isinstance(pref.state, ReadState):
                pref.state = UnreadState()
        return delivery

class DeliveryManager:
    strategies: Dict[DeliveryType, DeliveryStrategy] = {}

    @staticmethod
    def register_strategy(delivery_type: DeliveryType, strategy: DeliveryStrategy):
        DeliveryManager.strategies[delivery_type] = strategy

    @staticmethod
    def deliver(alert: Alert, user: User) -> NotificationDelivery:
        strategy = DeliveryManager.strategies.get(alert.delivery_type)
        if not strategy:
          
            strategy = DeliveryManager.strategies.get(DeliveryType.IN_APP)
        return strategy.deliver(alert, user)


DeliveryManager.register_strategy(DeliveryType.IN_APP, InAppDelivery())

class ReminderService:
    @staticmethod
    def trigger_reminders() -> Dict[str, Any]:
        """
        Iterate alerts and deliver reminders to users according to the alert's reminder_frequency and user's snooze/read state.
        Returns a summary for the run.
        """
        deliveries_sent = 0
        skipped_snoozed = 0
        skipped_inactive = 0
        skipped_no_audience = 0
        now = now_utc()
        for alert in list(DB["alerts"].values()):
            if not alert.reminder_enabled:
                continue
            if not alert.is_active(now):
                skipped_inactive += 1
                continue
            audience = AudienceRegistrar.resolve_audience(alert)
            if not audience:
                skipped_no_audience += 1
                continue
            for uid in audience:
                user = UserManager.get_user(uid)
                if not user:
                    continue
                key = (uid, alert.id)
                pref: UserAlertPreference = DB["user_alert_prefs"].get(key)
                if not pref:
                
                    pref = UserAlertPreference(user_id=uid, alert_id=alert.id, state=UnreadState())
                    DB["user_alert_prefs"][key] = pref
               
                pref.ensure_snooze_expired()
                if pref.is_snoozed_now():
                    skipped_snoozed += 1
                    continue
              
                last_delivery = None
                for d in reversed(DB["deliveries"]):
                    if d.alert_id == alert.id and d.user_id == uid:
                        last_delivery = d
                        break
                should_send = False
                if not last_delivery:
                    should_send = True
                else:
                    delta = now - last_delivery.delivered_at
                    freq = timedelta(minutes=alert.reminder_frequency_minutes)
                    if delta >= freq:
                        should_send = True
                if should_send:
                    DeliveryManager.deliver(alert, user)
                    deliveries_sent += 1
        return {
            "deliveries_sent": deliveries_sent,
            "skipped_snoozed": skipped_snoozed,
            "skipped_inactive": skipped_inactive,
            "skipped_no_audience": skipped_no_audience,
            "timestamp": now.isoformat(),
        }


class AnalyticsManager:
    @staticmethod
    def get_metrics() -> Dict[str, Any]:
        total_alerts = len(DB["alerts"])
        total_deliveries = len(DB["deliveries"])
        # read count = number of preferences in read state
        read_counts = sum(1 for p in DB["user_alert_prefs"].values() if isinstance(p.state, ReadState))
        snoozed_counts_per_alert: Dict[str, int] = {}
        severity_breakdown: Dict[str, int] = {s.value: 0 for s in Severity}
        for alert in DB["alerts"].values():
            severity_breakdown[alert.severity.value] = severity_breakdown.get(alert.severity.value, 0) + 1
            snoozed_counts_per_alert[alert.id] = sum(1 for p in DB["user_alert_prefs"].values() if p.alert_id == alert.id and p.is_snoozed_now())
        delivered_vs_read = {
            "delivered": total_deliveries,
            "read": read_counts,
        }
        return {
            "total_alerts": total_alerts,
            "delivered_vs_read": delivered_vs_read,
            "snoozed_counts_per_alert": snoozed_counts_per_alert,
            "severity_breakdown": severity_breakdown,
        }



def seed_data():
    
    DB["teams"].clear()
    DB["users"].clear()
    DB["alerts"].clear()
    DB["deliveries"].clear()
    DB["user_alert_prefs"].clear()

    
    eng = TeamManager.add_team("Engineering")
    mkt = TeamManager.add_team("Marketing")

    
    alice = UserManager.add_user("Alice", team_id=eng.id)
    bob = UserManager.add_user("Bob", team_id=mkt.id)
    carol = UserManager.add_user("Carol", team_id=eng.id)

   
    AlertManager.create_alert(
        title="System Maintenance Tonight",
        message="We will perform maintenance at 23:00 UTC. Services may be intermittently unavailable.",
        severity=Severity.WARNING,
        delivery_type=DeliveryType.IN_APP,
        visibility=VisibilityType.ORGANIZATION,
        reminder_enabled=True,
        reminder_frequency_minutes=120,
        start_time=now_utc(),
        expiry_time=now_utc() + timedelta(days=1),
    )

    AlertManager.create_alert(
        title="Engineering Standup Postponed",
        message="Daily standup at 10:00 is postponed today.",
        severity=Severity.INFO,
        delivery_type=DeliveryType.IN_APP,
        visibility=VisibilityType.TEAM,
        visibility_ids=[eng.id],
        reminder_enabled=True,
        reminder_frequency_minutes=120,
    )

    AlertManager.create_alert(
        title="Security Incident",
        message="Critical vulnerability discovered. Follow the containment procedure.",
        severity=Severity.CRITICAL,
        delivery_type=DeliveryType.IN_APP,
        visibility=VisibilityType.USER,
        visibility_ids=[alice.id],
        reminder_enabled=True,
        reminder_frequency_minutes=60,  
    )

seed_data()


class AlertCreateRequest(BaseModel):
    title: str
    message: str
    severity: Severity = Severity.INFO
    delivery_type: DeliveryType = DeliveryType.IN_APP
    visibility: VisibilityType = VisibilityType.ORGANIZATION
    visibility_ids: Optional[List[str]] = None
    start_time: Optional[datetime] = None
    expiry_time: Optional[datetime] = None
    reminder_enabled: bool = True
    reminder_frequency_minutes: int = 120

class AlertUpdateRequest(BaseModel):
    title: Optional[str] = None
    message: Optional[str] = None
    severity: Optional[Severity] = None
    delivery_type: Optional[DeliveryType] = None
    visibility: Optional[VisibilityType] = None
    visibility_ids: Optional[List[str]] = None
    start_time: Optional[datetime] = None
    expiry_time: Optional[datetime] = None
    reminder_enabled: Optional[bool] = None
    reminder_frequency_minutes: Optional[int] = None
    archived: Optional[bool] = None


@app.post("/admin/alerts")
def admin_create_alert(payload: AlertCreateRequest):
    a = AlertManager.create_alert(
        title=payload.title,
        message=payload.message,
        severity=payload.severity,
        delivery_type=payload.delivery_type,
        visibility=payload.visibility,
        visibility_ids=payload.visibility_ids,
        start_time=payload.start_time,
        expiry_time=payload.expiry_time,
        reminder_enabled=payload.reminder_enabled,
        reminder_frequency_minutes=payload.reminder_frequency_minutes,
    )
    return {"alert": a}


@app.put("/admin/alerts/{alert_id}")
def admin_update_alert(alert_id: str, payload: AlertUpdateRequest):
    try:
        updated = AlertManager.update_alert(alert_id, **payload.dict())
        return {"alert": updated}
    except KeyError:
        raise HTTPException(status_code=404, detail="Alert not found")


@app.get("/admin/alerts")
def admin_list_alerts(severity: Optional[Severity] = Query(None), active_only: Optional[bool] = Query(None), audience: Optional[VisibilityType] = Query(None)):
    alerts = AlertManager.list_alerts(severity=severity, active_only=active_only, audience_filter=audience)
    return {"alerts": alerts}


@app.post("/system/trigger_reminders")
def trigger_reminders():
    summary = ReminderService.trigger_reminders()
    return {"summary": summary}


@app.get("/users/{user_id}/alerts")
def user_fetch_alerts(user_id: str, include_snoozed: bool = Query(False)):
    user = UserManager.get_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
   
    applicable_alerts = []
    for alert in DB["alerts"].values():
        if not alert.is_active():
            continue
        
        audience = AudienceRegistrar.resolve_audience(alert)
        if user_id not in audience:
            continue
        key = (user_id, alert.id)
        pref = DB["user_alert_prefs"].get(key)
        if not pref:
            pref = UserAlertPreference(user_id=user_id, alert_id=alert.id, state=UnreadState())
            DB["user_alert_prefs"][key] = pref
        pref.ensure_snooze_expired()
        if not include_snoozed and pref.is_snoozed_now():
            continue
        applicable_alerts.append({
            "alert": alert,
            "preference": {
                "state": pref.state.__class__.__name__,
                "last_read_at": pref.last_read_at,
                "snoozed_until": pref.snoozed_until,
            }
        })
    return {"alerts": applicable_alerts}


@app.post("/users/{user_id}/alerts/{alert_id}/snooze")
def user_snooze_alert(user_id: str, alert_id: str):
    user = UserManager.get_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    alert = DB["alerts"].get(alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    key = (user_id, alert_id)
    pref = DB["user_alert_prefs"].get(key)
    if not pref:
        pref = UserAlertPreference(user_id=user_id, alert_id=alert_id, state=UnreadState())
        DB["user_alert_prefs"][key] = pref
    pref.snooze_for_today()
    return {"result": "snoozed", "snoozed_until": pref.snoozed_until}


@app.post("/users/{user_id}/alerts/{alert_id}/read")
def user_mark_read(user_id: str, alert_id: str):
    user = UserManager.get_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    key = (user_id, alert_id)
    pref = DB["user_alert_prefs"].get(key)
    if not pref:
        raise HTTPException(status_code=404, detail="User alert preference not found")
    pref.mark_read()
    return {"result": "marked_read", "last_read_at": pref.last_read_at}


@app.post("/users/{user_id}/alerts/{alert_id}/unread")
def user_mark_unread(user_id: str, alert_id: str):
    user = UserManager.get_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    key = (user_id, alert_id)
    pref = DB["user_alert_prefs"].get(key)
    if not pref:
        raise HTTPException(status_code=404, detail="User alert preference not found")
    pref.mark_unread()
    return {"result": "marked_unread"}

@app.get("/admin/deliveries")
def admin_list_deliveries():
    return {"deliveries": DB["deliveries"]}


@app.get("/analytics")
def analytics():
    return AnalyticsManager.get_metrics()


@app.get("/teams")
def list_teams():
    return {"teams": TeamManager.list_teams()}

@app.get("/users")
def list_users():
    return {"users": UserManager.list_users()}


@app.post("/system/seed")
def system_seed():
    seed_data()
    return {"result": "seeded"}


@app.get("/alerts")
def get_alerts():
    """List all alerts (simple view)."""
    return [
        {"id": a.id, "title": a.title, "message": a.message, "severity": a.severity.value}
        for a in DB["alerts"].values()
    ]

@app.get("/alerts/{alert_id}")
def get_alert(alert_id: str):
    """Fetch single alert by ID."""
    alert = DB["alerts"].get(alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    return {
        "id": alert.id,
        "title": alert.title,
        "message": alert.message,
        "severity": alert.severity.value,
    }

@app.get("/preferences/{user_id}")
def get_user_preferences(user_id: str):
    """Fetch a user’s preferences for alerts."""
    user = UserManager.get_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    prefs = []
    for (uid, aid), pref in DB["user_alert_prefs"].items():
        if uid == user_id:
            prefs.append({
                "alert_id": aid,
                "state": pref.state.__class__.__name__,
                "last_read_at": pref.last_read_at,
                "snoozed_until": pref.snoozed_until,
            })
    return {"user_id": user_id, "preferences": prefs}


if __name__ == "__main__":
    import uvicorn
    print("Starting Alerting & Notification Platform (MVP) on http://127.0.0.1:8000")
    uvicorn.run("alertNotification:app", host="0.0.0.0", port=8000, reload=False)
