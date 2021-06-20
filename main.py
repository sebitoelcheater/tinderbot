import json
import math
from datetime import datetime, timedelta
from random import randint
from hammock import Hammock
from pymongo import MongoClient, UpdateOne
from simplejson.errors import JSONDecodeError
import time
import os

tinder = Hammock('https://api.gotinder.com')
token = os.getenv('X_AUTH_TOKEN')
blacklist = [
]

if token is None:
    auth = tinder.v2.auth.login.facebook.POST(json={'token': 'facebook_auth_token'}).json()
    token = auth['data']['api_token']

tinder = Hammock(
    'https://api.gotinder.com',
    headers={
        "Accept": "application/json",
        "app-version": "1020407",
        "platform": "web",
        "Referer": "https://tinder.com/",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_14_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/76.0.3809.132 Safari/537.36",
        "X-Auth-Token": token,
        "x-supported-image-formats": "webp,jpeg",
    })

profile = tinder.v2.profile.GET(params={'include': 'user'}).json()
my_id = profile['data']['user']['_id']
DB = MongoClient('localhost', 27017)['tinder']


def like(user):
    raw_like_response = tinder.like(user['_id']).GET()
    like_response = raw_like_response.json()
    return f"{user['name']}, {user['_id']}, {like_response['match']}, {like_response['likes_remaining']}"


def save_users(matches, do_update=True):
    updates = []
    for match in matches:
        user_id = match['person']['_id']
        if not do_update and DB['users'].find_one({'_id': user_id}) is not None:
            print('skipping user', user_id)
            continue
        user_data = get_user(user_id)
        updates.append(UpdateOne({'_id': user_id}, {'$set': user_data}, True))
        print(f'Saved user {user_id}, {user_data["distance_mi"]}')
    if len(updates) > 0:
        DB['users'].bulk_write(updates)


def save_conversations(matches):
    updates = []
    for match in matches:
        user_id = match['person']['_id']
        updates.append(UpdateOne({'_id': user_id}, {'$set': {'match': match}}, True))
        print(f'Saved match info of user {user_id}')
    if len(updates) > 0:
        DB['users'].bulk_write(updates)


def get_user(user_id):
    return tinder.user(user_id).GET(params={'locale': 'es-ES'}).json()['results']


def get_matches():
    updates = tinder.updates.POST(json={'last_activity_date': ''}).json()
    return updates['matches']


def shout(message, matches):
    for match in matches:
        actual_message = message(match)
        if actual_message is None:
            continue
        if not isinstance(actual_message, list):
            actual_message = [actual_message]
        for a_m in actual_message:
            user_id = match['_id']
            message_response = tinder.user.matches(user_id).POST(json={'message': a_m})
            print(message_response)


def get_girls_who_havent_spoken(matches):
    return filter(
        lambda match: len([m for m in match["messages"] if m["from"] != my_id]) == 0,
        matches
    )


def get_non_started_conversation_girls(matches):
    return filter(lambda match: len(match['messages']) == 0, matches)

def get_started_conversation_girls(matches):
    return filter(lambda match: len(match['messages']) > 0, matches)


def get_near_people(matches, radius=40):
    near_users = [u['_id'] for u in DB['users'].find({'distance_mi': {'$lte': radius}})]
    return filter(lambda match: match['person']['_id'] in near_users, matches)


def get_matches_where_ive_talked_but_she_doesnt(matches, max_messages=math.inf):
    return filter(
        lambda match: max_messages >= len(match['messages']) > 0 and len([m for m in match['messages'] if m['to'] == my_id]) == 0,
        matches
    )


def get_matches_whose_conversations_i_havent_responded_yet(matches):
    return filter(
        lambda match: len(match['messages']) > 0 and match['messages'][-1]['from'] != my_id,
        matches
    )


def girls_who_have_talked(matches):
    return filter(
        lambda match: any([message['from'] != my_id for message in match['messages']]),
        get_started_conversation_girls(matches)
    )


def girls_who_have_not_responded_my_last_message(matches):
    return filter(
        lambda match: match['messages'][-1]['from'] == my_id,
        get_started_conversation_girls(matches)
    )


def last_message_before(matches, hours_ago):
    date_ago = datetime.now() - timedelta(hours=hours_ago)
    return filter(
        lambda match: datetime.strptime(match['messages'][-1]['created_date'], "%Y-%m-%dT%H:%M:%S.%fZ") < date_ago,
        matches
    )


def not_in_blacklist(matches):
    return filter(
        lambda match: len(set.intersection(set(match['participants']), set(blacklist))) == 0,
        matches
    )


def custom_message(match):
    last_message = match['messages'][-1]['message']
    response = input(f'--------\nNombre: {match["person"]["name"]}\nMensaje: {last_message}\nrespuesta?: ')
    if response in [None, '']:
        return None
    return response


def a_b_testing_message(match):
    messages = [
        'No necesitas hacer más swipe, encontraste al indicado 🤗',
        'Ya puedo dejar de hacer swipe'
    ]
    rand = randint(0, len(messages) - 1)
    message = messages[rand]
    print(message)
    return message


# say_to_all('Hoola')


matches = get_matches()
# save_users(matches)
#save_users(matches, False)
save_conversations(matches)

with open('matches.json', 'w') as outfile:
    outfile.write(json.dumps(matches, indent=4))

if False:
    # 916 matches
    shout(
        lambda match: f'hola {match["person"]["name"]}, cómo estás?' if 'person' in match else 'Holaa, como estai?',
        get_matches_where_ive_talked_but_she_doesnt(matches)
    )

if True:
    shout(
        lambda match: ['creo que ya puedo dejar de dar likes 🙊', f'Cómo estai {match["person"]["name"][:4]}?'], # lambda match: 'creo que ya puedo eliminar a mis otros matchs 🙊',  # 'Ya puedo dejar de deslizar 🙊',
        get_non_started_conversation_girls(matches)
    )

if True:
    shout(
        lambda match: 'holi',
        last_message_before(girls_who_have_not_responded_my_last_message(matches), 24)
    )

if False:
    shout(
        lambda match: '☺️', # ['holaa', 'cómo estai?'],
        get_matches_whose_conversations_i_havent_responded_yet(matches)
    )

if False:
    shout(
        lambda match: [f'hola {match["person"]["name"]}', 'cómo estás?'],
        get_matches_where_ive_talked_but_she_doesnt(matches)
    )

if False:
    shout(
        custom_message,
        get_matches_whose_conversations_i_havent_responded_yet(matches)
    )

if False:
    shout(
        lambda match: 'holi',  # 'Ya puedo dejar de deslizar 🙊',
        not_in_blacklist(matches)
    )

if False:
    shout(
        lambda match: 'holi',
        girls_who_have_not_responded_my_last_message(matches)
    )

GOLD = False
if GOLD:
    file = open('log.txt', 'a+', encoding="utf-8")
    for teaser in tinder.v2('fast-match').teasers.GET().json()['data']['results']:
        string = like(teaser['user'])
        print(string)
        file.write(string + "\n")
    file.close()

recommendations = tinder.user.recs.GET().json()

# like everyone
LIKE = False
while LIKE and 'results' in recommendations and len(recommendations['results']) > 0:
    file = open('log.txt', 'a+', encoding="utf-8")
    for rec in recommendations['results']:
        user = rec['user']
        try:
            time.sleep(0.2)
            string = like(user)
            print(string)
            file.write(string + "\n")
        except JSONDecodeError as e:
            print(raw_like_response.status_code, 'Too Many Requests')
    recommendations = tinder.user.recs.GET().json()
    file.close()
print('no profiles left to like')
