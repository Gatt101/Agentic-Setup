from __future__ import annotations

from langchain_core.tools import tool

_LEVEL_DESCRIPTIONS = {
    "RED": {
        "urgency_plain": "This is a serious injury that needs immediate hospital care.",
        "what_happens": "You will likely need emergency treatment, possibly surgery or specialist review.",
        "healing_time": "Recovery may take several months with professional medical supervision.",
    },
    "AMBER": {
        "urgency_plain": "This injury needs prompt attention at an urgent care clinic today.",
        "what_happens": "A doctor will assess you, possibly take more X-rays, and may fit a splint or cast.",
        "healing_time": "Most injuries at this level heal in 6–10 weeks with proper care.",
    },
    "GREEN": {
        "urgency_plain": "This is a minor injury that can be managed with rest and careful home care.",
        "what_happens": "Self-care with RICE (Rest, Ice, Compression, Elevation) and a follow-up appointment.",
        "healing_time": "Expect recovery within 4–6 weeks.",
    },
}

_WARNING_SIGNS = [
    "Increasing pain or swelling that is not improving",
    "Numbness, tingling, or loss of feeling in the affected area",
    "Skin turning white, blue, or cold around the injury",
    "Fever above 38°C (100.4°F)",
    "Splint or cast feels too tight",
    "Unable to move fingers or toes below the injury",
]

_FAQ = [
    {
        "question": "Can I take pain medication?",
        "answer": "Over-the-counter paracetamol (acetaminophen) is generally safe. Avoid ibuprofen or aspirin without asking your doctor first, especially if surgery is possible.",
    },
    {
        "question": "Should I keep the area elevated?",
        "answer": "Yes. Keep the injured limb raised above heart level as much as possible for the first 48 hours to reduce swelling.",
    },
    {
        "question": "When can I return to work or school?",
        "answer": "This depends on your job and the severity of your injury. Your doctor will advise you at your next appointment.",
    },
    {
        "question": "Will I need surgery?",
        "answer": "Not necessarily. Many fractures heal well with a cast or splint. Your treating doctor will decide based on your X-rays.",
    },
    {
        "question": "What should I eat to help healing?",
        "answer": "Eat foods rich in calcium (dairy, leafy greens), vitamin D (eggs, fortified milk), and protein (meat, legumes). Stay well-hydrated.",
    },
]


async def get_patient_education_impl(
    diagnosis: str,
    triage_level: str,
    body_part: str = "",
    patient_age: int = 40,
) -> dict:
    level = triage_level.strip().upper()
    level_info = _LEVEL_DESCRIPTIONS.get(level, _LEVEL_DESCRIPTIONS["AMBER"])
    location_phrase = f" in your {body_part}" if body_part else ""

    plain_summary = (
        f"You have been assessed for a possible {diagnosis}{location_phrase}. "
        f"{level_info['urgency_plain']} "
        f"{level_info['what_happens']} "
        f"{level_info['healing_time']}"
    )

    age_note = ""
    if patient_age >= 65:
        age_note = (
            "Because of your age, bones may take a little longer to heal. "
            "A bone-density check may also be recommended to reduce future fracture risk."
        )
    elif patient_age < 18:
        age_note = (
            "Growing bones heal well but need monitoring to ensure normal development continues. "
            "Keep all follow-up appointments and let your parent or guardian know about any new symptoms."
        )

    return {
        "diagnosis": diagnosis,
        "triage_level": level,
        "plain_summary": plain_summary,
        "age_specific_note": age_note,
        "what_to_do_now": level_info["what_happens"],
        "warning_signs": _WARNING_SIGNS,
        "faq": _FAQ,
        "do_not_list": [
            "Do NOT put weight on the injured area without medical clearance",
            "Do NOT remove any splint, cast, or bandage without doctor's advice",
            "Do NOT massage directly over the injury site",
            "Do NOT apply heat in the first 48 hours",
        ],
        "reassurance": (
            "You are receiving the right care. Follow your doctor's instructions, "
            "keep all appointments, and contact the clinic if symptoms worsen."
        ),
    }


@tool("knowledge_get_patient_education")
async def get_patient_education(
    diagnosis: str,
    triage_level: str,
    body_part: str = "",
    patient_age: int = 40,
) -> dict:
    """Generate patient-friendly education content explaining their condition, what to expect, and warning signs."""
    return await get_patient_education_impl(diagnosis, triage_level, body_part, patient_age)


__all__ = ["get_patient_education", "get_patient_education_impl"]
