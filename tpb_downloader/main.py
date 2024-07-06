#!/usr/bin/env python3
import logging
import time
import urllib.parse
from datetime import timedelta
from typing import TypedDict, Optional


import requests
import typer
from babelfish import Language
from subliminal import scan_videos, download_best_subtitles, save_subtitles, region
from transmission_rpc import Client, Torrent


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


transmission_client = Client()

trackers = [
    "udp://tracker.coppersurfer.tk:6969/announce",
    "udp://9.rarbg.to:2920/announce",
    "udp://tracker.opentrackr.org:1337",
    "udp://tracker.internetwarriors.net:1337/announce",
    "udp://tracker.leechers-paradise.org:6969/announce",
    "udp://tracker.coppersurfer.tk:6969/announce",
    "udp://tracker.pirateparty.gr:6969/announce",
    "udp://tracker.cyberia.is:6969/announce",
]


class TorrentInfo(TypedDict):
    magnet_link: str
    name: str
    size_in_gb: int
    seeders: int
    leechers: int
    info_hash: str


def __build_magenet_link_from_pirate_bay_result(result: dict) -> str:
    return (
        "magnet:?xt=urn:btih:"
        + result["info_hash"]
        + "&dn="
        + urllib.parse.quote_plus(result["name"])
        + "&tr="
        + "&tr=".join([urllib.parse.quote_plus(t) for t in trackers])
    )


def query_pirate_bay_api(imdb_id: str) -> Optional[TorrentInfo]:
    response = requests.get(f"https://apibay.org/q.php?q={imdb_id}")
    if not response.ok:
        raise Exception(
            f"Failed to query pirate bay api. status code: {response.status_code}"
        )

    response_json = response.json()
    results_with_1080p = [
        result
        for result in response_json
        if "1080" in result["name"].lower()
        if int(result["seeders"]) > 0
        and int(result["leechers"]) > 0
        and int(result["size"]) < 3 * 1024 * 1024 * 1024
    ]
    if not results_with_1080p:
        return None
    result = results_with_1080p[0]
    magnet_link = __build_magenet_link_from_pirate_bay_result(result)
    return TorrentInfo(
        magnet_link=magnet_link,
        name=result["name"],
        size_in_gb=int(int(result["size"]) / 1024 / 1024 / 1024),
        seeders=int(result["seeders"]),
        leechers=int(result["leechers"]),
        info_hash=result["info_hash"],
    )


def queue_torrent_download(
    magnet_link: str,
    folder_path: str,
) -> Torrent:
    added_torrent_info = transmission_client.add_torrent(
        magnet_link, download_dir=folder_path
    )
    logger.info(f"Added torrent: {added_torrent_info.name}")
    while True:
        torrent = transmission_client.get_torrent(added_torrent_info.id)
        logger.info(
            f"Download progress: {torrent.progress}%. Download rate: {torrent.rate_download} MB/s. Upload rate: {torrent.rate_upload} MB/s"
        )
        if torrent.status == "seeding":
            logger.info("Download complete")
            return added_torrent_info
        time.sleep(5)


def queue_subtitles_download(folder_path: str):
    region.configure("dogpile.cache.dbm", arguments={"filename": "cachefile.dbm"})
    # assuming the movie got downloaded in the past hour
    videos = scan_videos(folder_path, age=timedelta(hours=1))
    subtitles = download_best_subtitles(videos, {Language("eng")})
    for v in videos:
        logger.info(f"Saving subtitles for {v}")
        save_subtitles(v, subtitles[v])


app = typer.Typer()


@app.command()
def movie(imdb_id: str, download_path: str):
    logger.info(f"Downloading {imdb_id} to {download_path}")
    torrent_info = query_pirate_bay_api(imdb_id=imdb_id)
    if torrent_info:
        logger.info(
            f"Found torrent: {torrent_info.get('name')}. Size: {torrent_info.get('size_in_gb')} GB. Seeders: {torrent_info.get('seeders')}. Leechers: {torrent_info.get('leechers')}"
        )
        queue_torrent_download(
            magnet_link=torrent_info.get("magnet_link"),
            folder_path=download_path,
        )
        queue_subtitles_download(folder_path=download_path)
    else:
        print("No 1080p torrents found")


@app.command()
def series():
    raise NotImplemented("series download not implemented")


if __name__ == "__main__":
    app()
