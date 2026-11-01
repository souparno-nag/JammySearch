import praw
from praw.reddit import Reddit, Subreddit

from app.config import settings


# Set up Reddit client
def setup_reddit_client() -> Reddit:
    reddit = praw.Reddit(
        client_id=settings.reddit_client_id,
        client_secret=settings.reddit_client_secret.get_secret_value(),
        user_agent=settings.reddit_user_agent,
    )
    return reddit


# Obtain a subreddit
def obtain_subreddit(subreddit_name: str) -> Subreddit:
    reddit = setup_reddit_client()
    subreddit = reddit.subreddit(subreddit_name)
    return subreddit
