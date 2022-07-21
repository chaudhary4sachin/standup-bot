import slack
import os
from pathlib import Path
from dotenv import load_dotenv
from flask import Flask
from slackeventsapi import SlackEventAdapter
import userids

env_path = Path('.') / '.env'
load_dotenv(dotenv_path=env_path)

app = Flask(__name__)
slack_event_adapter = SlackEventAdapter(os.environ['SIGNING_SECRET'],
                                        '/slack/events', app)

client = slack.WebClient(token=os.environ['SLACK_TOKEN'])
BOT_ID = client.api_call("auth.test")["user_id"]

users = {}
user_counter_dict = {}


def get_channel_users_list(channel_id):
    response = client.conversations_members(channel=channel_id)
    all_users = response.get("members")
    # Remove app's own user id
    all_users.remove(userids.sub_sachin_app_user_id)
    return all_users


def send_msge_to_users(users_list):
    users_channel_dict = {}
    for user in users_list:
        response = ask_yesterday_updates(to_user=user)
        channel = response.get('channel')
        users_channel_dict[user] = channel
        update_user_counter(channel,1)
    return users_channel_dict


def get_user_name_from_id(user_id):
    response = client.users_info(user=user_id)
    return response.get("user").get("profile").get("display_name")


def get_conv_history(channel_id: str, limit: int):
    final_msge = ""
    response = client.conversations_history(channel=channel_id,
                                        inclusive=True, limit=limit)
    messages = response.get("messages")
    for message in messages[::-1]:
        final_msge += message.get("text")+"\n"
    return final_msge


def get_last_message_from_channel(users_channel_id: str):
    '''
    Use only the channel id returned by send_msge_to_users(), user_id
    doesn't work here.
    :param channel_id: channel id of each individual in the app
    :param limit: Number of messages to be returned
    :return: conversation history
    '''
    response = get_conv_history(users_channel_id, limit=6)
    return response.get("messages")[0].get("user"), response.get(
        "messages")[0].get("text")


def post_message_in_channel(channel_to, user_from, message):
    '''
    Use this method to post message in a channel once the status is received from the user.
    :param channel_id:
    :param message:
    :return:
    '''
    user_name = get_user_name_from_id(user_id=user_from)

    client.chat_postMessage(channel=channel_to, text=message,
                            username=f"Standup updates from {user_name}")


def ask_yesterday_updates(to_user):
    return client.chat_postMessage(channel=to_user, text="*What did you do "
                                                   "yesterday?* "
                                                         ":white_check_mark:")


def ask_today_updates(to_user):
    client.chat_postMessage(channel=to_user, text="\n*What will you do "
                                                  "today?*  :construction:")


def ask_blockers(to_user):
    client.chat_postMessage(channel=to_user, text="\n*Any blockers?* "
                                                  ":octagonal_sign:",
                            mrkdwn=True)


@slack_event_adapter.on('message')
def handle_user_response(payload):
    global user_counter_dict
    event = payload.get('event', {})
    user_id = event.get('user')
    channel = event.get('channel')
    if BOT_ID != user_id and channel != userids.sub_channel_user_id:
        if user_counter_dict[channel] == 1:
            ask_today_updates(to_user=channel)
            user_counter_dict[channel] = 2
        elif user_counter_dict[channel] == 2:
            ask_blockers(to_user=channel)
            user_counter_dict[channel] = 3
        elif user_counter_dict[channel] == 3 and not user_counter_dict[f"{channel}_flag"]:
            updates = get_conv_history(channel, 6)
            post_message_in_channel(channel_to=userids.sub_channel_user_id,
                                    user_from=user_id,
                                    message=updates)
            user_counter_dict[f"{channel}_flag"] = True


def update_user_counter(userid, counter):
    global user_counter_dict
    user_counter_dict[userid] = counter
    user_counter_dict[f"{userid}_flag"] = False


if __name__ == "__main__":
    users_id_list = get_channel_users_list(userids.sub_channel_user_id)
    # Ask users for updates.
    users = send_msge_to_users(users_list=users_id_list)
    app.run()


