"""Reusable transactional email templates."""

TEMPLATES = {
    "ACCOUNT_WELCOME": ("Welcome to KasaMukti", "Welcome to KasaMukti. Your circular recovery journey starts here."),
    "WASTE_SUBMISSION": ("Waste submission received", "Your waste submission {scanId} was received and is pending verification."),
    "COLLECTION_VERIFIED": ("Collection verified", "Your collection event was verified. {greenPoints} GreenPoints were earned."),
    "GREENPOINTS_EARNED": ("GreenPoints earned", "You earned {greenPoints} GreenPoints for a verified environmental action."),
    "CAMPAIGN_ANNOUNCEMENT": ("New KasaMukti campaign", "{campaignName} is now available in your area."),
    "HAZARDOUS_WASTE_ALERT": ("Hazardous waste alert", "A critical hazardous-waste scan requires municipal attention: {scanId}."),
    "RECOVERY_READY_BATCH": ("Recovery-ready batch", "Material batch {batchId} is ready for recovery matching."),
    "RECOVERY_REQUEST": ("Recovery request", "Recovery request {requestId} requires attention."),
    "RECOVERY_COMPLETED": ("Recovery completed", "Recovery for batch {batchId} has been completed."),
    "ANALYTICS_ALERT": ("Municipal analytics alert", "{message}"),
    "MATCHING_OPPORTUNITY": ("New recovery opportunity", "A recovery opportunity is available for batch {batchId}."),
    "RECOVERY_REQUEST_STATUS": ("Recovery request status updated", "Recovery request {requestId} is now {status}."),
    "PICKUP_SCHEDULED": ("Pickup scheduled", "Pickup for batch {batchId} is scheduled for {scheduledAt}."),
    "MATERIAL_RECEIVED": ("Material received", "Material batch {batchId} has been received."),
}


def render(event_type: str, data: dict) -> tuple[str, str]:
    if event_type not in TEMPLATES:
        return "KasaMukti notification", "A KasaMukti event requires your attention."
    subject, template = TEMPLATES[event_type]
    values = {"eventType": event_type, **data}
    try:
        return subject, template.format_map(values)
    except KeyError:
        return subject, f"KasaMukti event {event_type} requires your attention."
