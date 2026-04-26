import requests, os
from bs4 import BeautifulSoup
from readability import Document
from datetime import datetime
from config import TELEGRAM_TOKEN, CHAT_ID, SOURCES


# ===== 主任务 =====
def run_job():

    date = datetime.utcnow().strftime("%Y-%m-%d")

    SEEN_FILE = f"seen_{date}.txt"

    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE, "r") as f:
            seen_links = set(f.read().splitlines())
    else:
        seen_links = set()

    # ===== 发送（分段）=====
    def send(msg):
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        MAX = 3500

        parts = [msg[i:i+MAX] for i in range(0, len(msg), MAX)]

        for part in parts:
            try:
                r = requests.post(
                    url,
                    json={
                        "chat_id": CHAT_ID,
                        "text": part
                    },
                    timeout=10
                )
                print("发送状态:", r.status_code)
            except Exception as e:
                print("发送失败:", e)

    # ===== 提取链接 =====
    def get_links(url):
        try:
            r = requests.get(url, timeout=10)
            soup = BeautifulSoup(r.text, "html.parser")
            links = []

            for a in soup.find_all("a", href=True):
                href = a["href"]

                if any(x in href for x in [
                    "instagram","facebook","linkedin","youtube",
                    "signup","newsletter","account","subscribe",
                    "issue","preview","checklist","read-watch","bsky"
                ]):
                    continue

                if (
                    href.startswith("http")
                    and len(href) > 50
                    and ("/news/" in href or "/202" in href)
                    and "/t/" not in href
                ):
                    links.append(href)

            return list(dict.fromkeys(links))[:5]

        except:
            return []

    # ===== 抓正文 =====
    def fetch_article(url):
        try:
            r = requests.get(url, timeout=10)
            doc = Document(r.text)
            title = doc.title()

            html = doc.summary()
            soup = BeautifulSoup(html, "html.parser")
            text = soup.get_text()

            return title, text
        except:
            return None, None

    # ===== 总结 =====
    def summarize(text):
        prompt = f"""
你是艺术行业情报分析员，请提取关键信息：

1. 发生了什么（1句话）
2. 涉及谁（人 / 机构）
3. 为什么重要（行业意义）

控制在300字以内，中文输出：

{text[:2000]}
"""

        url = "https://open.bigmodel.cn/api/paas/v4/chat/completions"

        headers = {
            "Authorization": "Bearer 你的token保持不变",
            "Content-Type": "application/json"
        }

        data = {
            "model": "glm-4-flash",
            "messages": [{"role": "user", "content": prompt}]
        }

        try:
            r = requests.post(url, headers=headers, json=data, timeout=30)
            res = r.json()
            if "choices" in res:
                return res["choices"][0]["message"]["content"]
            else:
                return "【GLM错误】" + str(res)
        except:
            return text[:200]

    # ===== 主流程 =====
    folder = f"data/{date}"
    os.makedirs(folder, exist_ok=True)

    md = f"# 每日艺术信息 {date}\n\n"

    for source in SOURCES:
        print("抓列表:", source)
        links = get_links(source)

        for link in links:
            if link in seen_links:
                print("已跳过:", link)
                continue

            print("抓文章:", link)

            title, text = fetch_article(link)

            print("正文长度:", len(text) if text else 0)

            if not text or len(text) < 200:
                continue

            summary = summarize(text)
            seen_links.add(link)

            md += f"""## {title}

【英文原文片段】
{text[:800]}

【中文总结】
{summary}

🔗 原文：{link}

---

"""

    # ===== 保存 =====
    file_path = f"{folder}/daily.md"
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(md)

    print("已生成:", file_path)

    # ===== 保存记录 =====
    with open(SEEN_FILE, "w") as f:
        f.write("\n".join(seen_links))

    # ===== 推送 =====
    send(md)


# ===== 执行入口 =====
if __name__ == "__main__":
    print("开始执行任务...")
    run_job()
