# SPDX-FileCopyrightText: 2026 SidusNare
# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileContributor: Claude Opus 5.5 (AI-generated)

"""Self-contained Spotlight.js HTML gallery for photo libraries."""

import html as html_lib
from pathlib import Path

from plexapi.photo import Photo

from plexdo.console import clean_text
from plexdo.constants import LOG
from plexdo.paths import PathMapper, identity
from plexdo.photos import photo_file_path


def _gallery_css() -> str:
    """Return the embedded CSS for the photo gallery."""
    return """
    :root {
      --bg:     #0d0d0d;
      --surf:   #141414;
      --accent: #a0835c;
      --text:   #e0e0e0;
      --muted:  #4a4a4a;
      --gap:    4px;
      --thumb:  192px;
    }
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      background: var(--bg);
      color: var(--text);
      font-family: system-ui, -apple-system, sans-serif;
      min-height: 100vh;
    }
    #hdr {
      display: flex;
      align-items: baseline;
      gap: 1.2rem;
      padding: 1.2rem 2rem;
      background: var(--surf);
      border-bottom: 1px solid #1c1c1c;
      position: sticky;
      top: 0;
      z-index: 10;
    }
    #hdr h1 {
      font-size: .9rem;
      font-weight: 600;
      letter-spacing: .1em;
      text-transform: uppercase;
      color: var(--accent);
    }
    #hdr .total {
      font-size: .75rem;
      color: var(--muted);
    }
    .album { padding: 1.6rem 2rem 0.4rem; }
    .album-hdr {
      display: flex;
      align-items: baseline;
      gap: .7rem;
      padding-bottom: .5rem;
      margin-bottom: .8rem;
      border-bottom: 1px solid #1c1c1c;
    }
    .album-hdr h2 {
      font-size: .7rem;
      letter-spacing: .1em;
      text-transform: uppercase;
      color: var(--muted);
      font-weight: 500;
    }
    .album-hdr .n { font-size: .65rem; color: #333; }
    .grid {
      display: flex;
      flex-wrap: wrap;
      gap: var(--gap);
    }
    .grid a {
      display: block;
      width: var(--thumb);
      height: var(--thumb);
      overflow: hidden;
      flex-shrink: 0;
      border-radius: 2px;
    }
    .grid img {
      width: 100%;
      height: 100%;
      object-fit: cover;
      display: block;
      transition: transform .3s ease, opacity .3s ease;
    }
    .grid a:hover img { transform: scale(1.06); opacity: .8; }
    @media (prefers-reduced-motion: reduce) {
      .grid img { transition: none; }
    }
    """


def _gallery_photo_anchor(
    photo: Photo, map_path: PathMapper = identity
) -> list[str]:
    """Return HTML lines for a single Spotlight.js photo anchor.

    Uses the Plex server filesystem path for both href and src so no
    references to the Plex HTTP server appear in the output.  Photos with
    no resolvable path are skipped (returns an empty list), consistent with
    write_m3u behaviour.
    """
    file_path = photo_file_path(photo)
    if not file_path:
        LOG.debug("Skipping photo '%s': no server file path", photo.title)
        return []
    esc = html_lib.escape
    path = esc(map_path(file_path))
    title = esc(clean_text(photo.title or ""))
    taken = esc(str(getattr(photo, "originallyAvailableAt", "") or ""))
    return [
        f'      <a class="spotlight" href="{path}"',
        f'         data-title="{title}" data-description="{taken}">',
        f'        <img src="{path}" loading="lazy" alt="{title}">',
        "      </a>",
    ]


def _gallery_album_section(
    album_name: str, album_photos: list[Photo], map_path: PathMapper = identity
) -> list[str]:
    """Return HTML lines for one album section."""
    esc = html_lib.escape
    lines: list[str] = [
        '  <section class="album">',
        '    <div class="album-hdr">',
        f"      <h2>{esc(album_name)}</h2>",
        f'      <span class="n">{len(album_photos)}</span>',
        "    </div>",
        '    <div class="grid spotlight-group">',
    ]
    for photo in album_photos:
        lines.extend(_gallery_photo_anchor(photo, map_path))
    lines += ["    </div>", "  </section>"]
    return lines


def _group_photos_by_album(photos: list[Photo]) -> dict[str, list[Photo]]:
    """Group photos by parentTitle, using 'Uncategorised' as fallback."""
    groups: dict[str, list[Photo]] = {}
    for photo in photos:
        album = (
            clean_text(getattr(photo, "parentTitle", "") or "")
            or "Uncategorised"
        )
        groups.setdefault(album, []).append(photo)
    return groups


def write_gallery_html(
    photos: list[Photo],
    output_path: str,
    library_title: str,
    map_path: PathMapper = identity,
) -> None:
    """Write a Spotlight.js HTML5 gallery for a list of Photo objects.

    Photos are grouped by album (parentTitle).  The gallery uses CDN-hosted
    Spotlight.js for the lightbox; all image references are server filesystem
    paths - no Plex HTTP URLs appear in the output.
    """
    esc = html_lib.escape
    cdn = "https://cdn.jsdelivr.net/npm/spotlight.js"
    head = (
        [
            "<!DOCTYPE html>",
            '<html lang="en">',
            "<head>",
            '  <meta charset="UTF-8">',
            '  <meta name="viewport"'
            ' content="width=device-width, initial-scale=1">',
            f"  <title>{esc(library_title)}</title>",
            '  <link rel="stylesheet"'
            f' href="{cdn}/dist/css/spotlight.min.css">',
            "  <style>",
        ]
        + [f"  {line}" for line in _gallery_css().splitlines()]
        + [
            "  </style>",
            "</head>",
            "<body>",
            '  <header id="hdr">',
            f"    <h1>{esc(library_title)}</h1>",
            f'    <span class="total">{len(photos):,} photos</span>',
            "  </header>",
        ]
    )
    albums = _group_photos_by_album(photos)
    body = [
        line
        for name in sorted(albums)
        for line in _gallery_album_section(name, albums[name], map_path)
    ]
    foot = [
        f'  <script src="{cdn}/dist/js/spotlight.bundle.min.js"></script>',
        "</body>",
        "</html>",
        "",
    ]

    out = Path(output_path).expanduser()
    out.write_text("\n".join(head + body + foot), encoding="utf-8")
    LOG.info("Gallery written to %s (%d photos)", out, len(photos))
