#!/usr/bin/env python3

from termcolor import colored
# https://pypi.org/project/termcolor/

import argparse
import os
import requests


parser = argparse.ArgumentParser()
parser.add_argument('-u', '--user', help='echo the string you use here')
args = parser.parse_args()
if not args.user:
    raise Exception('user is required to go on')


API_BASE_URL = 'https://api.github.com'
DEFAULT_HEADERS = {}

GH_TOKEN = os.environ['GH_TOKEN']
if GH_TOKEN:
    DEFAULT_HEADERS['Authorization'] = 'token {}'.format(GH_TOKEN)

ALLOWED_EVENTS = [
    'IssueCommentEvent',
    'IssuesEvent',
    'PullRequestEvent',
    'PullRequestReviewCommentEvent',
    'GollumEvent',  # Triggered when a Wiki page is created or updated.
]


def _user_activity(url):
    response = requests.get(url, headers=DEFAULT_HEADERS)
    header_links = requests.utils.parse_header_links(response.headers['Link'])
    header_links = {link['rel']: link['url'] for link in header_links}
    return response, header_links


def _increase(d, key):
    if key not in d:
        d[key] = 0
    d[key] = d[key] + 1
    return d


def _issue_comment(event):
    payload = event.get('payload', {})
    return '(issue: {}) "{}"'.format(
        payload.get('issue', {}).get('number'),
        payload.get('comment', {}).get('body')
    )


def _issue(event):
    payload = event.get('payload', {})
    return '[action:{}] ({}) {}'.format(
        payload.get('action', '').upper(),
        payload.get('issue', {}).get('number'),
        payload.get('issue', {}).get('title'),
    )


def _pull_request(event):
    payload = event.get('payload', {})
    # if payload.get('action') != 'opened':
    #     return None

    return '[action:{}] {}({})'.format(
        payload.get('action', '').upper(),
        payload.get('pull_request', {}).get('title'),
        payload.get('pull_request', {}).get('number'),
    )


def _pull_request_review_comment(event):
    payload = event.get('payload', {})
    return '[pr: {}({})] "{}"'.format(
        payload.get('pull_request', {}).get('title'),
        payload.get('pull_request', {}).get('number'),
        payload.get('comment', {}).get('body'),
    )


def _wiki_event(event):
    pages = event.get('payload', {}).get('pages', [])
    first_page = pages[0] if len(pages) > 0 else None # FIXME get all pages

    return '[action:{}] {}'.format(
        first_page.get('action', {}),
        first_page.get('title', {}),
    )


EVENT_READ = {
    'IssueCommentEvent': _issue_comment,
    'IssuesEvent': _issue,
    'PullRequestEvent': _pull_request,
    'PullRequestReviewCommentEvent': _pull_request_review_comment,
    'GollumEvent': _wiki_event
}


def _read_event(activity, event_repo, event_type, event):
    event_result = EVENT_READ[event_type](event)
    if event_result:
        event_activity = activity.get(event_type, {})
        event_list = event_activity.get(event_repo, [])
        event_list.append(event_result)
        event_activity[event_repo] = event_list
        activity[event_type] = event_activity
    return activity


def _read(result, response):
    if response.status_code != 200:
        raise Exception('unexpected error from github api, status code: {}, response content: {}'
                        .format(response.status_code, response.content))
    for event in response.json():
        event_type = event.get('type')
        event_repo = event.get('repo', {}).get('name')
        if event_type in ALLOWED_EVENTS:
            result['summary'] = _increase(
                result.get('summary', {}), event_type)
            result['activity'] = _read_event(
                result.get('activity', {}), event_repo, event_type, event)
    return result


url = '{}/users/{}/events'.format(API_BASE_URL, args.user)
response, header_links = _user_activity(url)
result = _read({}, response)
next_link = header_links['next']
while next_link:
    response, header_links = _user_activity(next_link)
    result = _read(result, response)
    next_link = header_links.get('next')

def _pretty_print_str(s, level, color):
    tab = '\t' * level
    print(colored('{}- {}'.format(tab, s), color))

def _pretty_print_list(l, level, color):
    tab = '\t' * level
    for i in l:
        print(colored('{}- {}'.format(tab, i), color))

def _pretty_print_dict(d, level = 0):
    tab = '\t' * level
    next_level = level + 1
    for key, value in d.items():
        print(colored('{}- {}'.format(tab, key), 'blue', attrs=['bold']))
        if isinstance(value, list):
            _pretty_print_list(value, next_level, 'white')
        elif isinstance(value, dict):
            _pretty_print_dict(value, next_level)
        else:
            _pretty_print_str(value, next_level, 'white')

# import pprint;pprint.pprint(result)
_pretty_print_dict(result)
