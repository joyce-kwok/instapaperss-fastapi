import os, time, secrets
import concurrent.futures
import feedparser
import requests, json
import urllib.parse
from httpx import AsyncClient
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import Optional, Annotated
from pydantic import BaseModel, Field
from requests_oauthlib import OAuth1Session
from fastapi import Depends, Form, FastAPI, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.responses import PlainTextResponse, RedirectResponse, ORJSONResponse

app = FastAPI()
security = HTTPBasic() 

app.state.access_token = None
app.state.token_secret = None

CONSUMER_KEY = os.getenv('CONSUMER_KEY')
CONSUMER_SECRET = os.getenv('CONSUMER_SECRET')

base_url = 'https://www.instapaper.com/api/1/'
batch_size = 8

class HousekeepRequest(BaseModel):
    action: str
    amount: int = Field(default=None)
    bytag: Optional[str] = Field(default=None)
    removefromarchived: Optional[bool] = Field(default=False)
    skipstarred: Optional[bool] = Field(default=True)

class loginRequest(BaseModel):
    insta_username: str
    insta_password: str

def save_new_items_to_instapaper(feed_url, source, existurls):
    """Save new items from an RSS feed to Pocket in batches.
    
    Args:
        feed_url: URL of the RSS feed to process
        batch_size: Number of items to send in each batch (default: 6)
    """
    url = base_url + 'bookmarks/add'
    print(f"Checking {feed_url}...")
    # print (f"Existing URLs {existurls}...")
    
    try:
        feed = feedparser.parse(feed_url)
        if not feed.entries:
            print("No entries found in feed.")
            return
            
        # Process items in reverse order (oldest first)
        entries = reversed(feed.entries)
        batch = []
        
        for entry in entries:
            published_datetime = parsedate_to_datetime(entry.published)
            unix_timestamp = int(published_datetime.timestamp())
            # print(f"Checking if {entry.link} is a new link... ")
            if entry.link not in existurls:
               print(f"{entry.link} is a new link and will be pushed")
               print(f"Original Published Time: {entry.published}, Unix Timestamp (in integer): {unix_timestamp}")
               tags_obj = [{"name": source}]
               params = {
                   "url": entry.link,
                   "title": entry.title,
                   "description": entry.summary,
                   "tags": json.dumps(tags_obj)   # other optional params like folder_id, resolve_final_url, etc.
                }
               session = make_instapaper_client()
               resp = session.post(url, data=params)
               print(resp.text)
    except Exception as e:
        print(f"Error processing feed {feed_url}: {str(e)}")

def search_existing(source):
    urlist = []
    url = base_url + 'bookmarks/list'
    params = {
        'tag': source,
        'limit': 500
    }
    session = make_instapaper_client()
    response = session.post(url, data=params)
    print(f"Calling list bookmarks API to search saved posts, response code is {response.status_code}")
    if response.status_code == 200:
       articles = response.json()
       article_list = [item for item in articles if item.get("type") == "bookmark"]
       if len(article_list) > 0:
          last_item = article_list[0] # Returns the full last item dict
          latest = datetime.fromtimestamp(int(last_item['time']), tz=timezone.utc)
          print(f"Last updated: {latest}")
          for article in article_list:
              urlist.append(article['url'])
       else:
          print("No existing articles for this news source") 
          print(f"Last updated: {latest}")
    else:
        urlist.append('error')
    return urlist, response.status_code

def retrievehousekeepItems(amount, skipStarred, getArchived, tag):
    url = base_url + 'bookmarks/list'
    housekeep_ids = []
    params = {
        'tag': tag,
        'limit': 500,
        'folder_id': 'archive' if getArchived else 'unread'
    }
    session = make_instapaper_client()
    response = session.post(url, data=params)
    print(f"Calling retrieve API for housekeeping, response code is {response.status_code}")
    if response.status_code == 200:
       articles = response.json()
       print("request parameters: " + str(params))
       print("request url: " + url)
       print("response text: " + response.text)
       article_list = [
        item
        for item in articles
        if item.get("type") == "bookmark"
        and (not skipStarred or item.get("starred") == "0")
      ]
       if len(article_list) > 0:
          temp = article_list[-amount:]
          for article in temp:
              housekeep_ids.append(article['bookmark_id'])
       else:
          print("No articles found for housekeeping")
    else:
        print("Error retrieving articles for housekeeping")
    return housekeep_ids

async def archive_items(amount, skipStarred, bytag):
    items = retrievehousekeepItems(amount, skipStarred, False, bytag)
    print(f"Items to archive: {items}")
    url = base_url + 'bookmarks/archive'
    for itemid in items:
        params = {
                "bookmark_id": itemid
               }
        session = make_instapaper_client()
        resp = session.post(url, data=params)
        print("request parameters: " + str(params))
        print("request url: " + url)
        print("response text: " + resp.text)
    return "Archive completed"  

async def delete_items(amount, skipStarred, removefromarchived, bytag):
    items = retrievehousekeepItems(amount, skipStarred, removefromarchived, bytag)
    print(f"Items to delete: {items}")
    url = base_url + 'bookmarks/delete'
    for itemid in items:
        params = {
                "bookmark_id": itemid
               }
        session = make_instapaper_client()
        resp = session.post(url, data=params)
    return "Deletion completed"

def authenticate(
    credentials: Annotated[HTTPBasicCredentials, Depends(security)],
):
    auth = return_token(credentials.username, credentials.password)

    if auth["code"] != 0:
        print("Could not authenticate with Instapaper")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Basic"},
        )
    app.state.access_token = auth["access_token"]
    app.state.token_secret = auth["access_token_secret"]
    return auth["code"] == 0


@app.get("/")
async def root():
    return {"message": "kept awake"}

@app.head("/healthcheck")
async def head_item():
    return {}

@app.post("/housekeep", response_class=PlainTextResponse)
async def housekeep(request: HousekeepRequest, verification: bool = Depends(authenticate)):
    if verification:
        res = ''
        if request.action == 'archive':
            res = await archive_items(request.amount, request.skipstarred, request.bytag)
        elif request.action == 'delete':
            res = await delete_items(request.amount, request.skipstarred, request.removefromarchived, request.bytag)
        else:
            return "Invalid request parameters"
        return res
    else:
        return "Unauthorized due to incorrect credentials"

@app.get("/save/{source}", response_class=PlainTextResponse)
async def save_source(source: str, verification: bool = Depends(authenticate)):
    """Save specific feed source"""
    print(f"Data source: {source}")
    if verification: 
       # Load RSS_FEEDS from JSON config
       with open('config.json') as config_file:
            config = json.load(config_file)
            RSS_FEEDS = config['RSS_FEEDS']
       if source not in RSS_FEEDS:
          return f"Invalid source. Available sources: {', '.join(RSS_FEEDS.keys())}"
       existurls, code = search_existing(source)
       if code == 200:
          with concurrent.futures.ThreadPoolExecutor() as executor:
            list(executor.map(lambda feed: save_new_items_to_instapaper(feed, source, existurls), RSS_FEEDS[source]))
          return f"Saved {source} feeds to pocket"
       else:
          return f"Cannot retrieve saved {source} feeds at the moment. Will not update news in this run."


def return_token(username, password):
    url = base_url + 'oauth/access_token'

    oauth = OAuth1Session(
        CONSUMER_KEY,
        client_secret=CONSUMER_SECRET
    )

    # xAuth parameters go in POST body
    params = {
        "x_auth_username": username,
        "x_auth_password": password,
        "x_auth_mode": "client_auth",
    }
    resp = oauth.post(url, data=params)
    
    if resp.status_code != 200:
        return {
            "code": -1,
            "detail": "Failed to obtain access token"
            }

    # Response is qline-like: oauth_token=...&oauth_token_secret=...
    parts = dict(
        item.split("=", 1) for item in resp.text.strip().split("&")
    )
    access_token = parts["oauth_token"]
    access_token_secret = parts["oauth_token_secret"]

    # You should store these for this user (DB, session, etc.)
    return {
        "code": 0,
        "access_token": access_token,
        "access_token_secret": access_token_secret,
    }


def make_instapaper_client():
    return OAuth1Session(
        CONSUMER_KEY,
        client_secret=CONSUMER_SECRET,
        resource_owner_key= app.state.access_token,
        resource_owner_secret= app.state.token_secret,
        signature_method="HMAC-SHA1",
    )

    




