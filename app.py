import os
from slack_bolt import App
from slack_bolt.oauth.oauth_settings import OAuthSettings
from slack_sdk.oauth.installation_store import FileInstallationStore
from slack_sdk.oauth.state_store import FileOAuthStateStore
from pymongo import MongoClient 
import re

"""
SLACK_CLIENT_ID = 4343233466758.4362483114609
SLACK_CLIENT_SECRET=a10750d5d20b1019e37b04e090e4f259
SLACK_SIGNING_SECRET=ad1d64008afe01a25caa2e71ddcd1e94
"""
oauth_settings = OAuthSettings(
    client_id=os.environ.get("SLACK_CLIENT_ID"), 
    client_secret=os.environ.get("SLACK_CLIENT_SECRET"), 
    scopes=["channels:history", "chat:write", "commands", "groups:history", "im:history", "mpim:history", "users.profile:read", "users:read", "channels:read", "groups:read", "mpim:read", "im:read"],
    installation_store=FileInstallationStore(base_dir="./data/installations"),
    state_store=FileOAuthStateStore(expiration_seconds=600, base_dir="./data/states")
)

def get_database(): 
    CONNECTION_STRING = "mongodb+srv://slack_follow:slack_f0ll0w@cluster0.9idsapx.mongodb.net/?retryWrites=true&w=majority"
    client = MongoClient(CONNECTION_STRING)
    return client['slack']

# Initializes your app with your bot token and signing secret
app = App(
    signing_secret=os.environ.get("SLACK_SIGNING_SECRET"), 
    oauth_settings=oauth_settings
)

# make sure that you can only follow a user once 
# check if you've already followed a user in the mongodb and if yes, then send a message
@app.command("/follow")
def follow(ack, respond, command, client): 
    ack() 
    to_follow = command['text'].split('|')[0][2:]
    curr_user = command['user_id']
    follows_user = dbname['follows_user']
    if list(follows_user.find({'user': to_follow, "follows_user": curr_user})) != []: 
        pass
        # client.chat_postEphemeral(channel=command['channel_id'], text="You are already following this user!", user=curr_user)
    else:
        to_insert = {"user": to_follow, "follows_user": curr_user}
        follows_user.insert_one(to_insert)
        # client.chat_postEphemeral(channel=command['channel_id'], text="You are now following this user!", user=curr_user)

@app.message(re.compile('.*?'))
def message_from_user(message, client):
    user_id = message['user']
    follows_user = dbname['follows_user'] 
    followers = list(follows_user.find({'user': user_id}))
    for item in followers: 
        client.chat_postMessage(channel=item['follows_user'], text="@" + client.users_info(user=item['user'])['user']['name'] + " has posted" + '\n' + client.chat_getPermalink(channel=message['channel'], message_ts=message['ts'])['permalink'])


def get_all_folders(user_id): 
    folders = dbname['folders']
    folders = list(folders.find({'user': user_id}))
    options = []
    for item in folders: 
        temp = {"text": {"type": "plain_text", "text": item['folder']['value']}, "value": item['folder']['value']}
        options.append(temp)
    return options 


@app.shortcut("addtofolder")
def add_to_folder(ack, shortcut, client): 
    ack() 
    permalink = client.chat_getPermalink(channel=shortcut['channel']['id'], message_ts=shortcut['message_ts'])['permalink']
    messages = dbname['messages']
    user_id = shortcut['user']['id']
    to_insert = {"user": user_id, "timestamp": shortcut['message_ts'], "channel_id": shortcut['channel']['id'], "channel_name": shortcut['channel']['name'], "permalink": permalink, "text": shortcut['message']['text']}
    if list(messages.find(to_insert)) == []: 
        messages.insert_one(to_insert)
    options = get_all_folders(user_id)
    if options == []: 
        client.views_open(
            trigger_id = shortcut['trigger_id'],
            view={
                "type": "modal", 
                "title": {"type": "plain_text", "text": "Save this message"},
                "callback_id": "choose_folder", 
                "submit": {
                    "type": "plain_text",
                    "text": "Submit"
                },
                "blocks": [
                    {
                        "type": "actions", 
                        "block_id": "addornew", 
                        "elements": [
                            {
                                "type": "button", 
                                "text": {
                                    "type": "plain_text", 
                                    "text": "Create new folder"
                                }, 
                                "value": "new_folder", 
                                "action_id": "new_folder"
                            }
                        ]
                    }
                ],
                "private_metadata": permalink
            }
        )
    else: 
        client.views_open(
            trigger_id = shortcut['trigger_id'],
            view={
                "type": "modal", 
                "title": {"type": "plain_text", "text": "Save this message"},
                "callback_id": "choose_folder", 
                "submit": {
                    "type": "plain_text",
                    "text": "Submit"
                },
                "blocks": [
                    {
                        "type": "actions", 
                        "block_id": "addornew", 
                        "elements": [
                            {
                                "type": "button", 
                                "text": {
                                    "type": "plain_text", 
                                    "text": "Create new folder"
                                }, 
                                "value": "new_folder", 
                                "action_id": "new_folder"
                            }, 
                            {
                                "type": "static_select", 
                                "placeholder": {
                                    "type": "plain_text", 
                                    "text": "Add to existing folder"
                                },
                                "action_id": "add_message_to_folder",
                                "options": options
                            }
                        ]
                    }
                ],
                "private_metadata": permalink
            }
        )


@app.view("choose_folder")
def choose_folder(ack, body):
    ack() 
    user_id = body['user']['id']
    folder = body['view']['state']['values']['addornew']['add_message_to_folder']['selected_option']['value']
    permalink = body['view']['private_metadata']
    folder_messages = dbname['folder_messages']
    to_insert = {"user": user_id, "folder": folder, "permalink": permalink}
    folder_messages.insert_one(to_insert)

    
@app.action("add_message_to_folder")
def add_message_to_folder(ack, body): 
    ack() 

@app.action("new_folder")
def new_folder(ack, body, logger, client): 
    ack() 
    client.views_update(
        view_id=body['container']['view_id'],
        view={
            "type": "modal", 
            "callback_id": "create_new_folder",
            "title": {
                "type": "plain_text", 
                "text": "Create a new folder"
            },
            "submit": {
                "type": "plain_text",
                "text": "Submit"
            },
            "blocks": [
                {
                    "type": "input",
                    "block_id": "create_new_folder",
                    "element": {
                        "type": "plain_text_input",
                        "action_id": "create_new_folder",
                        "placeholder": {
                            "type": "plain_text",
                            "text": "Input name for a new folder"
                        }
                    },
                    "label": {
                        "type": "plain_text",
                        "text": "Create new folder"
                    }
                }
            ], 
            "private_metadata": body['view']['private_metadata']
        }
    )

@app.view("create_new_folder")
def create_new_folder(ack, body, logger): 
    ack()
    user_id = body['user']['id']
    folder_name = body['view']['state']['values']['create_new_folder']['create_new_folder']
    folders = dbname['folders']
    to_insert = {"user": user_id, "folder": folder_name}
    folders.insert_one(to_insert)

    permalink = body['view']['private_metadata']
    folder_messages = dbname['folder_messages']
    to_insert = {"user": user_id, "folder": folder_name['value'], "permalink": permalink}
    folder_messages.insert_one(to_insert)




@app.event("app_home_opened")
def handle_app_home_opened_events(body, logger, client): 
    user_id = body['event']['user']
    options = get_all_folders(user_id)
    if options == []:
        client.views_publish(
            user_id=user_id, 
            view={
                "type": "home", 
                "blocks": [
                    {
                        "type": "section", 
                        "text": {
                            "type": "mrkdwn", 
                            "text": "This page will display all your folders!"
                        }
                    }
                ]
            }
        )

    else: 
        client.views_publish(
            user_id=user_id, 
            view={
                "type": "home", 
                "blocks": [
                    {
                        "type": "actions", 
                        "elements": [
                            {
                                "type": "static_select", 
                                "placeholder": {
                                    "type": "plain_text", 
                                    "text": "Select a folder"
                                },
                                "action_id": "open_folder",
                                "options": options
                            }
                        ]
                    }
                ]
            }
        )
    

@app.action("open_folder")
def open_folder(ack, body, logger, client): 
    ack() 
    user_id = body['user']['id']
    options = get_all_folders(user_id)
    temp = {
                "type": "actions",
                "elements": [
                    {
                        "type": "static_select", 
                        "placeholder": {
                            "type": "plain_text", 
                            "text": "Select a folder"
                        },
                        "action_id": "open_folder",
                        "options": options
                    }
                ]
            }
    folder = body['actions'][0]['selected_option']['value']
    folder_messages = dbname['folder_messages'] 
    messages = list(folder_messages.find({'user': user_id, 'folder': folder}))
    sections = [temp]
    
    for message in messages:
        permalink = message['permalink']
        messages_db = dbname['messages']
        msg_dict = messages_db.find_one({'user': user_id, 'permalink': permalink})        
        channel_id = msg_dict['channel_id']
        channel_name = msg_dict['channel_name']
        user_id = msg_dict['user']
        msg_time = msg_dict['timestamp'].split('.')[0]
        user_profile = client.users_profile_get(user=user_id)
        
        
        channel = {"type": "section", "fields": [{"type": "mrkdwn", "text": "<https://slack.com/app_redirect?channel=" + channel_id + "| " + "#" + channel_name + ">"}]}
        sections.append(channel)
        user_info = {"type": "context", "elements": [{"type": "image", "image_url": user_profile['profile']['image_24'], "alt_text": "profile photo"}, {"type": "mrkdwn", "text": "<@" + user_id + "> " + "<!date^" + msg_time + "^{date} at {time}| >"}]}
        sections.append(user_info)
        post = {"type": "section", "fields": [{"type": "mrkdwn", "text": msg_dict['text'] + '\n<' + msg_dict['permalink']+"|go to message>"}]}
        sections.append(post)
        divider = {"type": "divider"}
        sections.append(divider)

    client.views_update(
        view_id=body['container']['view_id'], 
        view={
            "type": "home",
            "blocks": sections
        }
    )


# Start your app
if __name__ == "__main__":
    dbname = get_database()
    app.start(port=int(os.environ.get("PORT", 3000)))

