# ==================================================================================
# BLOCK 7: INTERACTIVE REVIEW SHELL
# ==================================================================================
import os
import json
from IPython.display import display, clear_output, HTML
import ipywidgets as widgets

# Configuration
BOOKS_DIR = "/content/books"

def load_book_data(slug):
    """Loads story positions for a specific book."""
    path = os.path.join(BOOKS_DIR, slug, "story_positions.json")
    if not os.path.exists(path):
        print(f"❌ File not found: {path}")
        return None, path, None

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Load Full_Text.md for story content
    full_text_path = os.path.join(BOOKS_DIR, slug, "Full_Text.md")
    full_text = None
    if os.path.exists(full_text_path):
        with open(full_text_path, "r", encoding="utf-8") as f:
            full_text = f.read()

    return data, path, full_text

def save_book_data(data, path):
    """Saves updated data back to JSON."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"✅ Saved changes to {os.path.basename(path)}")

def run_review_shell():
    """Interactive review shell with proper Colab UI."""
    print("=== INTERACTIVE STORY REVIEW SHELL ===\n")

    # 1. Select Book
    subfolders = [f for f in os.listdir(BOOKS_DIR) if os.path.isdir(os.path.join(BOOKS_DIR, f))]
    if not subfolders:
        print("No books found in /books/")
        return

    book_dropdown = widgets.Dropdown(
        options=subfolders,
        description='Book:',
        disabled=False,
    )

    mode_radio = widgets.RadioButtons(
        options=['Flagged Only (Recommended)', 'All Stories'],
        description='Mode:',
        disabled=False
    )

    start_button = widgets.Button(
        description='Start Review',
        button_style='success',
        icon='check'
    )

    display(widgets.VBox([book_dropdown, mode_radio, start_button]))

    # Callback when user clicks start
    def on_start_clicked(b):
        clear_output(wait=True)
        book_slug = book_dropdown.value
        mode = mode_radio.value

        data, json_path, full_text = load_book_data(book_slug)
        if not data:
            return

        # Filter Stories
        all_stories = list(data.items())
        flagged_stories = [(t, d) for t, d in all_stories if d.get("status") == "NEEDS_REVIEW"]

        print(f"📚 Book: {book_slug}")
        print(f"Total Stories: {len(all_stories)}")
        print(f"🔴 Flagged for Review: {len(flagged_stories)}")
        print(f"🟢 Auto-Approved: {len(all_stories) - len(flagged_stories)}\n")

        queue = flagged_stories if "Flagged" in mode else all_stories
        if not queue:
            print("🎉 No stories to review!")
            return

        # Create interactive review UI
        create_review_ui(queue, data, json_path, full_text)

    start_button.on_click(on_start_clicked)


def create_review_ui(queue, data, json_path, full_text):
    """Create the main review interface."""
    state = {'current_idx': 0, 'modified': False}

    # UI Components
    output = widgets.Output()

    # Navigation buttons
    prev_btn = widgets.Button(description='← Previous', button_style='info')
    next_btn = widgets.Button(description='Next →', button_style='info')
    approve_btn = widgets.Button(description='✓ Approve', button_style='success')
    skip_btn = widgets.Button(description='Skip', button_style='warning')
    save_btn = widgets.Button(description='💾 Save & Exit', button_style='danger')

    # Keyword editor
    keyword_input = widgets.Textarea(
        placeholder='Enter keywords (comma separated)',
        description='Keywords:',
        layout=widgets.Layout(width='80%', height='80px')
    )
    update_kw_btn = widgets.Button(description='Update Keywords', button_style='primary')

    # Progress
    progress_label = widgets.HTML()

    def render_story():
        """Render current story details."""
        with output:
            clear_output(wait=True)
            if state['current_idx'] >= len(queue):
                print("🎉 Review Complete!")
                return

            title, info = queue[state['current_idx']]
            status = info.get("status", "UNKNOWN")
            confidence = info.get("confidence", 0.0)

            # Extract story text
            story_text = "Story text not available"
            if full_text and info.get("start_char", -1) != -1 and info.get("end_char", -1) != -1:
                story_text = full_text[info["start_char"]:info["end_char"]].strip()
                # Escape HTML and preserve line breaks
                story_text = story_text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('\n', '<br>')

            # Status color
            status_color = "red" if status == "NEEDS_REVIEW" else "green"

            # Build HTML display
            html = f"""
            <div style="border: 2px solid {status_color}; padding: 15px; margin: 10px 0; border-radius: 5px;">
                <h3 style="color: {status_color};">{title}</h3>
                <p><strong>Status:</strong> {status} | <strong>Confidence:</strong> {confidence:.2f} | <strong>Pages:</strong> {info.get('pages', 'N/A')}</p>

                <div style="background: #e8f4f8; padding: 15px; margin: 15px 0; border-radius: 3px; max-height: 400px; overflow-y: auto; border-left: 4px solid #0066cc;">
                    <h4>📖 Story Text</h4>
                    <div style="font-family: Georgia, serif; line-height: 1.6; white-space: pre-wrap;">
                        {story_text}
                    </div>
                </div>

                <div style="background: #f5f5f5; padding: 10px; margin: 10px 0; border-radius: 3px;">
                    <h4>📅 Temporal</h4>
                    <p><strong>Years:</strong> {', '.join(map(str, info.get('temporal', {}).get('years', []))) or 'None'}</p>
                    <p><strong>Centuries:</strong> {', '.join(map(str, info.get('temporal', {}).get('centuries', []))) or 'None'}</p>
                </div>

                <div style="background: #f5f5f5; padding: 10px; margin: 10px 0; border-radius: 3px;">
                    <h4>🌍 Locations</h4>
                    <p><strong>Cities:</strong> {', '.join(info.get('locations', {}).get('cities', [])) or 'None'}</p>
                    <p><strong>Countries:</strong> {', '.join(info.get('locations', {}).get('countries', [])) or 'None'}</p>
                </div>

                <div style="background: #f5f5f5; padding: 10px; margin: 10px 0; border-radius: 3px;">
                    <h4>🏷️ Topics</h4>
                    <p><strong>Primary:</strong> {', '.join(info.get('topics', {}).get('primary', [])) or 'None'}</p>
                    <p><strong>Secondary:</strong> {', '.join(info.get('topics', {}).get('secondary', [])) or 'None'}</p>
                </div>

                <div style="background: #fff3cd; padding: 10px; margin: 10px 0; border-radius: 3px;">
                    <h4>🔑 Keywords (Full List)</h4>
                    <p>{', '.join(info.get('keywords', [])) or 'None'}</p>
                </div>
            """

            # Add warnings if low confidence
            if confidence < 0.75:
                warnings = []
                if not info.get('temporal', {}).get('years'): warnings.append("No years detected")
                if not info.get('locations', {}).get('cities'): warnings.append("No specific locations")
                if not info.get('topics', {}).get('primary'): warnings.append("No primary topics")

                if warnings:
                    html += '<div style="background: #f8d7da; padding: 10px; margin: 10px 0; border-radius: 3px; color: #721c24;">'
                    html += '<h4>⚠️ Warnings</h4><ul>'
                    for w in warnings:
                        html += f'<li>{w}</li>'
                    html += '</ul></div>'

            html += '</div>'
            display(HTML(html))

            # Update keyword input with current keywords
            keyword_input.value = ', '.join(info.get('keywords', []))

            # Update progress
            progress_label.value = f"<h4>Story {state['current_idx'] + 1} of {len(queue)}</h4>"

    # Button callbacks
    def on_approve(b):
        title, info = queue[state['current_idx']]
        info['status'] = 'REVIEWED'
        info['confidence'] = 1.0
        data[title] = info
        state['modified'] = True
        with output:
            print("✅ Story approved!")
        state['current_idx'] += 1
        render_story()

    def on_skip(b):
        state['current_idx'] += 1
        render_story()

    def on_prev(b):
        if state['current_idx'] > 0:
            state['current_idx'] -= 1
            render_story()

    def on_next(b):
        if state['current_idx'] < len(queue) - 1:
            state['current_idx'] += 1
            render_story()

    def on_update_keywords(b):
        title, info = queue[state['current_idx']]
        new_kws = [k.strip() for k in keyword_input.value.split(',') if k.strip()]
        info['keywords'] = new_kws
        info['status'] = 'REVIEWED'
        info['confidence'] = 1.0
        data[title] = info
        state['modified'] = True
        with output:
            print(f"✅ Keywords updated! ({len(new_kws)} total)")
        render_story()

    def on_save(b):
        if state['modified']:
            save_book_data(data, json_path)
            with output:
                print("\n✅ All changes saved to disk!")
        else:
            with output:
                print("\n💡 No changes to save.")

    # Connect buttons
    approve_btn.on_click(on_approve)
    skip_btn.on_click(on_skip)
    prev_btn.on_click(on_prev)
    next_btn.on_click(on_next)
    update_kw_btn.on_click(on_update_keywords)
    save_btn.on_click(on_save)

    # Layout
    nav_buttons = widgets.HBox([prev_btn, next_btn, skip_btn, approve_btn, save_btn])
    keyword_edit = widgets.HBox([keyword_input, update_kw_btn])

    # Display
    display(progress_label)
    display(output)
    display(nav_buttons)
    display(keyword_edit)

    # Initial render
    render_story()


# ==================================================================================
# UNCOMMENT TO RUN:
# ==================================================================================
run_review_shell()
