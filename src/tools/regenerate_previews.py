"""Script to regenerate preview images for existing posts.

Usage:
    python -m tools.regenerate_previews [--force]

By default regenerates previews only for posts missing `nahladovy_obrazok`.
Pass `--force` to regenerate for all posts.
"""
import sys
from pathlib import Path

from student_network import create_app
from student_network.repositories.posts import get_all_posts, update_post
from student_network.thumbnail_service import generate_thumbnail_from_file, get_file_icon_svg
import base64
import uuid


def main(force: bool = False) -> int:
    app = create_app()
    with app.app_context():
        posts = get_all_posts()
        total = len(posts)
        updated = 0

        for row in posts:
            post_id = int(row['id'])
            nazov = row['nazov']
            popis = row['popis'] or ''
            current_preview = row['nahladovy_obrazok'] or ''
            subor = row['subor'] or ''
            subor_povodny = row['subor_povodny_nazov'] or ''

            if not force and current_preview:
                # skip posts that already have a preview unless forced
                print(f"Skipping post {post_id} (has preview)")
                continue

            if not subor:
                print(f"Skipping post {post_id} (no file)")
                continue

            # determine extension
            ext = Path(subor_povodny).suffix.lower() or Path(subor).suffix.lower()

            new_preview = ''

            # build stored filename if present
            stored_name = Path(subor).name if subor else ''

            # prefer generating a thumbnail image file and storing its relative path
            # attempt to generate a thumbnail data-URI and save it as PNG under POST_IMAGE_UPLOAD_DIR
            file_full_path = None
            if stored_name:
                # try both post_images and post_files locations
                candidate1 = Path(app.config['POST_IMAGE_UPLOAD_DIR']) / stored_name
                candidate2 = Path(app.config['POST_FILE_UPLOAD_DIR']) / stored_name
                if candidate1.exists():
                    file_full_path = candidate1
                elif candidate2.exists():
                    file_full_path = candidate2

            if file_full_path is None:
                # fallback: nothing to generate from
                if ext == '.pdf':
                    # try to reference file in POST_FILE_UPLOAD_DIR anyway
                    file_full_path = Path(app.config['POST_FILE_UPLOAD_DIR']) / stored_name

            thumbnail_uri = None
            if file_full_path and file_full_path.exists():
                thumbnail_uri = generate_thumbnail_from_file(file_full_path, ext)

            if thumbnail_uri and thumbnail_uri.startswith('data:image'):
                # decode and save as PNG file
                try:
                    header, b64 = thumbnail_uri.split(',', 1)
                    data = base64.b64decode(b64)
                    thumb_name = f"thumb_{post_id}_{uuid.uuid4().hex}.png"
                    thumb_path = Path(app.config['POST_IMAGE_UPLOAD_DIR']) / thumb_name
                    thumb_path.write_bytes(data)
                    new_preview = f"uploads/post_images/{thumb_name}"
                except Exception:
                    new_preview = get_file_icon_svg(ext)
            else:
                # if no thumbnail generated, for images we can use stored path, else use SVG icon
                if ext in {'.jpg', '.jpeg', '.png', '.webp', '.gif'} and subor:
                    new_preview = subor
                else:
                    new_preview = get_file_icon_svg(ext)

            # persist update
            try:
                update_post(
                    post_id=post_id,
                    nazov=nazov,
                    popis=popis,
                    nahladovy_obrazok=new_preview,
                    subor=subor,
                    subor_povodny_nazov=subor_povodny,
                )
            except Exception as exc:
                print(f"Failed to update post {post_id}: {exc}")
                continue

            updated += 1
            print(f"Updated post {post_id} preview")

        print(f"Done: processed {total} posts, updated {updated}")
    return 0


if __name__ == '__main__':
    force_flag = '--force' in sys.argv[1:]
    raise SystemExit(main(force=force_flag))
