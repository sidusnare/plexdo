#!/bin/sh
# SPDX-License-Identifier: GPL-3.0-or-later
#
# Turn every man/*.scd page into a GitHub wiki page in Markdown:
#
#     scdoc -> roff -> pandoc -> GitHub-flavoured Markdown
#
# Usage: tools/wiki-pages.sh SOURCE_DIR OUTPUT_DIR
#
# man/plexdo-wait.1.scd becomes OUTPUT_DIR/plexdo-wait.md, the wiki page
# plexdo-wait; the section number is dropped, since no two pages share a
# name. A reference such as plexdo-list-users(1) becomes a link to that
# page, and a reference to a page that does not exist is an error rather
# than a broken link.
#
# Each page opens with GENERATED_MARK in an HTML comment, which the wiki
# does not display. The publishing workflow deletes a wiki page only when it
# carries that mark and its source is gone, so pages written by hand are
# never touched.

set -eu

GENERATED_MARK="Generated from"

if [ $# -ne 2 ]; then
    echo "usage: $0 SOURCE_DIR OUTPUT_DIR" >&2
    exit 2
fi
src_dir=$1
out_dir=$2

for tool in scdoc pandoc; do
    if ! command -v "$tool" >/dev/null 2>&1; then
        echo "$0: $tool is required but not installed" >&2
        exit 1
    fi
done

rm -rf "$out_dir"
mkdir -p "$out_dir"
scratch=$(mktemp -d)
trap 'rm -rf "$scratch"' EXIT

count=0
for source in "$src_dir"/*.scd; do
    [ -e "$source" ] || { echo "$0: no .scd files in $src_dir" >&2; exit 1; }
    # plexdo-wait.1.scd -> plexdo-wait
    page=$(basename "$source" .scd)
    page=${page%.*}
    if [ -e "$out_dir/$page.md" ]; then
        echo "$0: two sources would both become the page $page" >&2
        exit 1
    fi

    # Each step writes a file of its own rather than feeding a pipe, so a
    # failure anywhere stops the run instead of yielding a truncated page.
    scdoc < "$source" > "$scratch/page.roff"
    pandoc --from man --to gfm --output "$scratch/page.md" "$scratch/page.roff"
    {
        printf '<!-- %s %s by tools/wiki-pages.sh. Edits made on the wiki\n' \
            "$GENERATED_MARK" "$source"
        printf '     are overwritten: change the source in the repository. -->\n\n'
        # **plexdo-wait**(1) -> [**plexdo-wait**(1)](plexdo-wait)
        sed -E 's/\*\*(plexdo-[a-z0-9-]+)\*\*\(([0-9])\)/[**\1**(\2)](\1)/g' \
            "$scratch/page.md"
    } > "$out_dir/$page.md"
    count=$((count + 1))
done

# Every link made above must land on a page that was made too.
broken=$(grep -oh '](plexdo-[a-z0-9-]*)' "$out_dir"/*.md | sort -u |
    sed 's/^](//; s/)$//' | while read -r target; do
        [ -e "$out_dir/$target.md" ] || echo "$target"
    done)
if [ -n "$broken" ]; then
    echo "$0: references to pages that do not exist:" \
        "$(printf '%s' "$broken" | tr '\n' ' ')" >&2
    exit 1
fi

echo "wiki: $count pages written to $out_dir"
