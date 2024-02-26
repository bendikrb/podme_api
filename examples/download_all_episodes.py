import os
from podme_api.client import PodMeSchibstedClient

SCHIBSTED_PASSWORD = os.environ.get("SCHIBSTED_PASSWORD")
SCHIBSTED_EMAIL = os.environ.get("SCHIBSTED_EMAIL")
if not SCHIBSTED_PASSWORD or not SCHIBSTED_EMAIL:
    raise ValueError("Please set SCHIBSTED_EMAIL and SCHIBSTED_PASSWORD environment variables.")

client = PodMeSchibstedClient(SCHIBSTED_EMAIL, SCHIBSTED_PASSWORD)
client.login()

episodes = client.get_episode_list("big-5-med-nils-og-harald-2")

for episode in episodes:
    info = client.get_episode_info(episode.id)
    outtmpl = f"{info.podcastTitle} - {info.dateAdded.isoformat()} - {info.title}.%(ext)s"
    client.download_episode(outtmpl, info.streamUrl)
