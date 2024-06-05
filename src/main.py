"""
oViceからワークスペースのユーザー情報を取得し、入退室状況を通知するスクリプト
"""

import datetime
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from time import sleep
from urllib.error import HTTPError

GET_HOLIDAYS_API = "https://holidays-jp.github.io/api/v1/date.json"
OVICE_PUBLIC_API = "https://api.ovice.io/api/public/v1"
GET_WORKSPACES_API = f"{OVICE_PUBLIC_API}/organizations/workspaces"
GET_USERS_API = f"{OVICE_PUBLIC_API}/workspaces/workspace_users"
SLACK_WEBHOOK_API = os.environ["SLACK_WEBHOOK_API"]

HEADERS = {
    "client_id": os.environ["OVICE_CLIENT_ID"],
    "client_secret": os.environ["OVICE_CLIENT_SECRET"],
}
JST = datetime.timezone(datetime.timedelta(hours=9), "Asia/Tokyo")
WORK_START_TIME = datetime.time(hour=8, minute=0, second=0, tzinfo=JST)
WORK_END_TIME = datetime.time(hour=19, minute=0, second=0, tzinfo=JST)
NEW_YEAR_HOLIDAYS = {"12-31", "01-01", "01-02", "01-03", "01-04"}

try:
    with urllib.request.urlopen(
        url=urllib.request.Request(url=GET_WORKSPACES_API, headers=HEADERS)
    ) as response:
        workspaces = json.loads(s=response.read().decode("utf-8"))
except HTTPError as e:
    print("oVice パブリックAPIからworkspace情報の取得に失敗しました。")
    print(e)
    sys.exit(1)

target_workspace = workspaces[0]
query_params = urllib.parse.urlencode({"workspace_id": target_workspace["id"]})
get_users_req = urllib.request.Request(
    url=GET_USERS_API + f"?{query_params}", headers=HEADERS
)


def get_japan_holidays() -> dict[str, str]:
    try:
        with urllib.request.urlopen(url=GET_HOLIDAYS_API) as response:
            japan_holidays = json.loads(response.read().decode("utf-8"))
    except HTTPError as e:
        print("祝日APIの呼び出しでエラーが発生しました。")
        print(e)
        sys.exit(1)
    return japan_holidays


prev_user_statuses = None
holidays = get_japan_holidays()
last_holiday_update = datetime.datetime.now(tz=JST)


def lambda_handler(event, context):
    global prev_user_statuses
    global holidays
    current_datetime = datetime.datetime.now(tz=JST)
    current_date = current_datetime.date()

    # 業務時間内ならprev_usersだけ更新してLambdaを終了
    is_weekend = current_datetime.weekday() >= 5
    is_holiday = (
        current_date.isoformat() in holidays
        or current_date.strftime(format="%m-%d") in NEW_YEAR_HOLIDAYS
    )
    is_work_time = WORK_START_TIME <= current_datetime.timetz() <= WORK_END_TIME
    if not (is_weekend or is_holiday) and is_work_time:
        print("現在は業務時間内なのでスキップします。")
        prev_user_statuses = None
        return

    # oViceからユーザー情報を取得
    try:
        with urllib.request.urlopen(url=get_users_req) as response:
            users = json.loads(s=response.read().decode("utf-8"))
    except HTTPError as e:
        print("oVice パブリックAPIからユーザー情報の取得に失敗しました。")
        print(e)
        prev_user_statuses = None
        sys.exit(1)

    current_user_statuses = {
        user["id"]: (user["name"], 1 if user["status"] == "online" else 0)
        for user in users
    }

    if prev_user_statuses is not None:
        new_online_users = []
        exists_new_offline_or_away_users = False
        for user_id, (user_name, current_status) in current_user_statuses.items():
            _, prev_status = prev_user_statuses.get(user_id)
            if prev_status is not None:
                transition = (
                    current_status - prev_status
                )  # 1: 入室, -1: 退室, 0: 変化なし
                if transition == 1:
                    new_online_users.append(user_name)
                elif transition == -1:
                    exists_new_offline_or_away_users = True
            elif (
                current_status == 1
            ):  # 前回の状態がない（=新規登録された）ユーザがオンラインなら入室扱い
                new_online_users.append(user_name)

        current_online_users_count = sum(
            status for _, status in current_user_statuses.values()
        )
        message = None
        if new_online_users:
            message = (
                "\n".join(f"{user}さんが入室しました。" for user in new_online_users)
                + f"\n現在の人数：{current_online_users_count}"
            )
        elif exists_new_offline_or_away_users and current_online_users_count == 0:
            message = "現在は誰もいません。"

        if message is not None:
            try:
                urllib.request.urlopen(
                    urllib.request.Request(
                        url=SLACK_WEBHOOK_API,
                        data=json.dumps({"text": message}).encode("utf-8"),
                        headers={"Content-Type": "application/json"},
                        method="POST",
                    )
                )
            except HTTPError as e:
                print("Slack Webhook APIの呼び出しでエラーが発生しました。")
                print(e)
                prev_user_statuses = None
                sys.exit(1)
    prev_user_statuses = current_user_statuses
    # 祝日情報を前回取得から1か月以上経過していたら更新
    global last_holiday_update
    if current_datetime - last_holiday_update > datetime.timedelta(days=30):
        holidays = get_japan_holidays()
        last_holiday_update = current_datetime


if __name__ == "__main__":
    for _ in range(5):
        start_time = time.time()
        lambda_handler(None, None)
        elapsed_time = time.time() - start_time
        print(f"処理時間：{elapsed_time:.2f}秒")
        sleep(5)
