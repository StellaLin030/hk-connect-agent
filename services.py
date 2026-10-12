from copy import deepcopy

DATA_VERSION = "D2"

SOURCE_URL = (
    "https://www.had.gov.hk/rru/english/"
    "programmes/support_service_centres.htm"
)

# 每项依次为：ID、名称、中心所在行政区、一般查询电话、
# 是否在来源目录中明确列有中央电话传译服务。
CENTRE_ROWS = [
    (
        "cheer",
        "CHEER Centre",
        "Kwun Tong",
        "3106 3104",
        True,
    ),
    (
        "dream",
        "DREAM Centre",
        "Kowloon City",
        "3104 4044",
        False,
    ),
    (
        "hope",
        "HOPE Centre",
        "Wan Chai",
        "2836 3598",
        True,
    ),
    (
        "link",
        "LINK Centre",
        "Kwai Tsing",
        "3955 1555",
        False,
    ),
    (
        "idea",
        "IDEA Centre",
        "Sha Tin",
        "3101 5959",
        False,
    ),
    (
        "ylth",
        "Yuen Long Town Hall Support Service Centre for Ethnic Minorities",
        "Yuen Long",
        "2479 9757",
        False,
    ),
]

SERVICES = []

for service_id, name, district, phone, interpretation_listed in CENTRE_ROWS:
    categories = ["language_classes", "community_activities"]

    if interpretation_listed:
        categories.append("interpretation")

    SERVICES.append({
        "id": service_id,
        "name": name,
        "district": district,
        "categories": categories,
        "phone": phone,
        "phone_type": "general_enquiries",
        "source_url": SOURCE_URL,
        "source_checked_on": "2026-10-12",
        "data_version": DATA_VERSION,
        "target_group": "Ethnic minority residents; confirm individual eligibility.",
        "schedule": None,
        "fees": None,
        "eligibility_details": None,
        "availability": None,
        "evidence_note": (
            "Centre-level service categories from the government directory. "
            "Specific course languages, dates, vacancies and eligibility "
            "are not recorded here and must be confirmed with the centre. "
            "An unlisted category does not prove a service is unavailable."
        ),
    })

# 统一常见地区写法，避免 Shatin 与 Sha Tin 被当成不同地区。
DISTRICT_ALIASES = {
    "kwun tong": "Kwun Tong",
    "觀塘": "Kwun Tong",
    "观塘": "Kwun Tong",

    "kowloon city": "Kowloon City",
    "九龍城": "Kowloon City",
    "九龙城": "Kowloon City",

    "wan chai": "Wan Chai",
    "wanchai": "Wan Chai",
    "灣仔": "Wan Chai",
    "湾仔": "Wan Chai",

    "kwai tsing": "Kwai Tsing",
    "kwai chung": "Kwai Tsing",
    "葵青": "Kwai Tsing",
    "葵涌": "Kwai Tsing",

    "sha tin": "Sha Tin",
    "shatin": "Sha Tin",
    "沙田": "Sha Tin",

    "yuen long": "Yuen Long",
    "元朗": "Yuen Long",
}


def search_services(category, district=None):
    """按类别和中心所在地查询；None 表示不限制所在地。"""
    valid_categories = {
        "language_classes",
        "community_activities",
        "interpretation",
    }

    if not isinstance(category, str) or category not in valid_categories:
        return {"error": "Invalid category"}

    if district is not None and not isinstance(district, str):
        return {"error": "District must be a string or null"}

    normalized_district = None

    if district is not None:
        district_key = " ".join(district.strip().lower().split())

        if not district_key:
            return {"error": "Use null for an unrestricted district."}

        # 未收录地区保持原值，不擅自替换成其他地区或取消限制。
        normalized_district = DISTRICT_ALIASES.get(
            district_key,
            district.strip(),
        )

    matches = []

    for service in SERVICES:
        category_matches = category in service["categories"]
        district_matches = (
            normalized_district is None
            or service["district"] == normalized_district
        )

        if category_matches and district_matches:
            matches.append(deepcopy(service))

    return {
        "matches": matches,
        "count": len(matches),
        "query": {
            "category": category,
            "requested_district": district,
            "normalized_district": normalized_district,
        },
        "data_version": DATA_VERSION,
        "coverage_note": (
            f"This dataset contains {len(SERVICES)} selected centres, "
            "not all services in Hong Kong. No match means no matching "
            "record in this dataset, not that no real-world service exists."
        ),
        "location_note": (
            "District filtering uses the centre's physical location. "
            "It does not establish service coverage or user eligibility. "
            "Telephone interpretation may not require an in-person visit."
        ),
    }


def prepare_contact_draft(service_id, language, need_summary):
    """生成联系草稿，不发送消息，也不创建预约。"""
    service = next(
        (item for item in SERVICES if item["id"] == service_id),
        None,
    )

    if service is None:
        return {"error": "Unknown service ID. Search services first."}

    if language not in ("en", "zh"):
        return {"error": "Language must be en or zh."}

    if not isinstance(need_summary, str):
        return {"error": "Need summary must be text."}

    need_summary = need_summary.strip()

    if not need_summary or len(need_summary) > 1000:
        return {"error": "Need summary must contain 1–1000 characters."}

    if language == "en":
        draft = (
            f"Hello {service['name']},\n\n"
            f"{need_summary}\n\n"
            "Thank you for your help."
        )
    else:
        draft = (
            f"{service['name']} 您好：\n\n"
            f"{need_summary}\n\n"
            "感謝您的協助。"
        )

    return {
        "type": "contact_draft",
        "status": "draft_only",
        "service_id": service["id"],
        "service_name": service["name"],
        "general_enquiry_phone": service["phone"],
        "source_url": service["source_url"],
        "language": language,
        "draft": draft,
        "notice": "Draft only. Nothing has been sent or booked.",
    }
