import json
import streamlit as st
import hashlib
from datetime import datetime, timezone
from uuid import uuid4

from experiment_log import save_event
from openai import OpenAI, APIConnectionError, APIStatusError
from agent import run_turn, MODEL, PROMPT_VERSION
from services import SERVICES, DATA_VERSION


st.set_page_config(page_title="港伴 HK Connect", layout="centered")
st.title("港伴 HK Connect")
st.write("尋找香港社區服務 / Find community support in Hong Kong")
st.info(
    "課堂原型：請使用虛構例子。對話會傳送至 DeepSeek。"
    "本系統不會代你聯絡機構。"
)
st.caption(
    "目前收錄 6 個少數族裔支援中心，並非全港完整服務名單。"
    "參加資格須向機構確認。 / "
    "Covers 6 selected ethnic minority support centres. "
    "This is not a complete directory; confirm eligibility with the centre."
)

# history 保存模型所需的消息，包括工具调用及返回结果。
# chat 保存用于页面展示的对话。
if "history" not in st.session_state:
    st.session_state.history = []
    st.session_state.chat = []
    st.session_state.experiments = []

if st.button("開始新對話 / New conversation"):
    st.session_state.history = []
    st.session_state.chat = []
    st.rerun()

for message in st.session_state.chat:
    with st.chat_message(message["role"]):
        st.write(message["content"])

st.info(
    "基本服務查詢不需要你的姓名、詳細住址或身份證號碼，"
    "請勿在聊天中提供這些資料。"
    "機構正式報名時的資料要求，須向機構另行確認。\n\n"
    "Basic service searches do not require your name, exact home "
    "address or identity card number. Please do not enter these "
    "details in the chat. A centre may have separate information "
    "requirements for enrolment."
)
user_text = st.chat_input("描述你的需要 / Describe what you need")

if user_text:
    try:
        api_key = st.secrets["DEEPSEEK_API_KEY"]
    except (FileNotFoundError, KeyError):
        st.error("找不到 DEEPSEEK_API_KEY，請檢查密鑰配置。")
        st.stop()

    with st.chat_message("user"):
        st.write(user_text)

    client = OpenAI(
        api_key=api_key,
        base_url="https://api.deepseek.com",
        timeout=60.0,
        max_retries=0,
    )

    partial_record = {}

    # 保存本轮之前的完整上下文，方便之后复现实验。
    experiment = {
        "model": MODEL,
        "prompt_version": PROMPT_VERSION,
        "history_before": list(st.session_state.history),
        "input": user_text,
        "data_snapshot": SERVICES,
        "parameters": {
            "max_tokens": 1200,
            "thinking": "disabled",
            "max_model_calls": 3,
        },
        "experiment_id": uuid4().hex,
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "record": partial_record,
        "data_hash": hashlib.sha256(
            json.dumps(
                SERVICES,
                ensure_ascii=False,
                sort_keys=True,
            ).encode("utf-8")
        ).hexdigest(),
        "data_version": DATA_VERSION,
    }

    try:
        with st.spinner("正在處理你的需要……"):
            history, answer, record = run_turn(
                client,
                st.session_state.history,
                user_text,
                record=partial_record,
            )

        st.session_state.history = history
        st.session_state.chat.extend([
            {"role": "user", "content": user_text},
            {"role": "assistant", "content": answer},
        ])

        experiment["status"] = "completed"
        experiment["record"] = record

        with st.chat_message("assistant"):
            st.write(answer)

    except APIConnectionError:
        experiment["status"] = "connection_error"
        st.error("連接失敗或超時，本輪未加入對話，請稍後重試。")

    except APIStatusError as error:
        experiment["status"] = f"http_{error.status_code}"
        st.error(f"API 錯誤，狀態碼：{error.status_code}")

    except RuntimeError as error:
        experiment["status"] = "stopped"
        experiment["error"] = str(error)
        st.error(str(error))

    finally:
        client.close()
        st.session_state.experiments.append(experiment)

        try:
            save_event("run_finished", experiment)
        except OSError:
            st.warning(
                "本地記錄寫入失敗，請使用頁面的下載按鈕保存記錄。"
            )

if st.session_state.experiments:
    with st.expander("實驗記錄 / Experiment records"):
        st.json(st.session_state.experiments[-1])

    # st.download_button(
    #     "下載全部實驗記錄 / Download experiment records",
    #     data=json.dumps(
    #         st.session_state.experiments,
    #         ensure_ascii=False,
    #         indent=2,
    #     ),
    #     file_name="hk_connect_experiments.json",
    #     mime="application/json",
    # )

    st.caption(
        "記錄包含測試對話，請只使用虛構資料。"
        "關閉或重新整理頁面可能使記錄丟失，請及時下載。"
    )

# 从最近一次成功交互中提取联系草稿。
contact_draft = None

if st.session_state.chat and st.session_state.experiments:
    latest = st.session_state.experiments[-1]

    if latest.get("status") == "completed":
        steps = latest.get("record", {}).get("steps", [])

        for step in reversed(steps):
            result = step.get("result", {})

            if result.get("type") == "contact_draft":
                contact_draft = result
                break

if contact_draft:
    st.divider()
    st.subheader("核對聯絡草稿 / Review contact draft")

    st.write(contact_draft["service_name"])
    st.write(
        "一般查詢電話 / General enquiries: "
        + contact_draft["general_enquiry_phone"]
    )
    st.markdown(
        f"[官方資料 / Official source]"
        f"({contact_draft['source_url']})"
    )
    st.info(
        "尚未發送或預約，請先核對內容。"
        " / Nothing has been sent or booked. Please review the draft."
    )

    # 每次实验使用独立的控件编号，避免复用上一份草稿。
    draft_key = f"draft_{len(st.session_state.experiments)}"
    approved_key = f"{draft_key}_approved"

    edited_draft = st.text_area(
        "可直接修改 / Edit before saving",
        value=contact_draft["draft"],
        height=250,
        key=draft_key,
    )

    if st.button(
        "確認內容 / Confirm text",
        key=f"{draft_key}_confirm",
    ):
        if edited_draft.strip():
            st.session_state[approved_key] = edited_draft

            # 保存用户核对后的版本，供实验分析。
            latest["reviewed_draft"] = {
                "service_id": contact_draft["service_id"],
                "text": edited_draft,
                "status": "reviewed_not_sent",
            }
        else:
            st.warning("草稿不能為空。 / The draft cannot be empty.")

    # 确认之后再修改文字，需要重新确认才能下载。
    if (
        edited_draft.strip()
        and st.session_state.get(approved_key) == edited_draft
    ):
        st.download_button(
            "下載草稿 / Download draft",
            data=edited_draft,
            file_name="contact_draft.txt",
            mime="text/plain",
            key=f"{draft_key}_download",
        )
        st.caption(
            "請自行聯絡機構；下載不代表已發送。"
            " / Contact the centre yourself; downloading does not send it."
        )

if st.session_state.experiments:
    st.divider()
    st.subheader("本次測試評估 / Evaluate this test")

    current = st.session_state.experiments[-1]
    experiment_id = current["experiment_id"]

    st.caption(f"實驗編號：{experiment_id}")

    with st.form(f"evaluation_{experiment_id}"):
        expected = st.text_area(
            "本次預期行為 / Expected behaviour",
            placeholder="例如：查詢觀塘機構，但不能聲稱星期日有班。",
        )

        verdict = st.selectbox(
            "人工判定 / Your assessment",
            [
                "未評估 / Not evaluated",
                "通過 / Pass",
                "部分通過 / Partial pass",
                "未通過 / Fail",
            ],
        )

        notes = st.text_area(
            "觀察與原因 / Observations",
            placeholder="寫出實際看到的行為，以及符合或不符合預期之處。",
        )

        save_review = st.form_submit_button("保存評估 / Save assessment")

    if save_review:
        if verdict == "未評估 / Not evaluated":
            st.warning("請先選擇評估結果。")
        elif not expected.strip() or not notes.strip():
            st.warning("請填寫預期行為及觀察，讓判定有據可查。")
        else:
            current["evaluation"] = {
                "expected": expected.strip(),
                "verdict": verdict,
                "notes": notes.strip(),
                "reviewed_at_utc": datetime.now(timezone.utc).isoformat(),
            }

            try:
                save_event("human_review", current)
                st.success("評估已保存。")
            except OSError:
                st.warning(
                    "本地保存失敗，評估仍在本次頁面會話中，請下載記錄。"
                )

    # 放在所有修改操作之后，确保导出包含最新评估与草稿审核。
    st.download_button(
        "匯出完整實驗記錄 / Export full experiment records",
        data=json.dumps(
            st.session_state.experiments,
            ensure_ascii=False,
            indent=2,
        ),
        file_name="hk_connect_experiments.json",
        mime="application/json",
        key="export_full_experiments",
    )