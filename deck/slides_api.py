"""Helpers for editing the team deck in Google Slides through the service account (see CLAUDE.md, Progress deck). Small helpers that turn shapes into Google Slides API requests, in the Oct 15 deck style (inches)."""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
import config  # noqa: F401  (sets GOOGLE_APPLICATION_CREDENTIALS from .env)
import google.auth
from googleapiclient.discovery import build

PID = "1-wQADZx76ESW--hegJxXh0cmfvM0C9b7TkOz1WIRaqU"
IN = 914400
RED, DARK, MUTED, CARD_LINE, PINK = "990000", "222222", "6B6B6B", "E6E6E6", "FBEDED"

credentials, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/presentations"])
slides = build("slides", "v1", credentials=credentials).presentations()


def rgb(hex_color):
    return {"red": int(hex_color[0:2], 16) / 255, "green": int(hex_color[2:4], 16) / 255, "blue": int(hex_color[4:6], 16) / 255}


def props(page, x, y, w, h):
    return {"pageObjectId": page, "size": {"width": {"magnitude": w * IN, "unit": "EMU"}, "height": {"magnitude": h * IN, "unit": "EMU"}},
            "transform": {"scaleX": 1, "scaleY": 1, "translateX": x * IN, "translateY": y * IN, "unit": "EMU"}}


def rect(page, oid, x, y, w, h, fill="FFFFFF", line=CARD_LINE):
    return [{"createShape": {"objectId": oid, "shapeType": "RECTANGLE", "elementProperties": props(page, x, y, w, h)}},
            {"updateShapeProperties": {"objectId": oid, "shapeProperties": {
                "shapeBackgroundFill": {"solidFill": {"color": {"rgbColor": rgb(fill)}}},
                "outline": {"outlineFill": {"solidFill": {"color": {"rgbColor": rgb(line)}}}, "weight": {"magnitude": 0.75, "unit": "PT"}}},
                "fields": "shapeBackgroundFill,outline"}}]


def text(page, oid, x, y, w, h, runs, size=11, color=DARK, align="START", valign="TOP", spacing_after=0, bullets=False):
    """runs: a string, or a list of [text, {"bold": True, "color": "...", "size": n, "italic": True}] pieces."""
    if isinstance(runs, str):
        runs = [[runs, {}]]
    full = "".join(piece for piece, _ in runs)
    requests = [{"createShape": {"objectId": oid, "shapeType": "TEXT_BOX", "elementProperties": props(page, x, y, w, h)}},
                {"insertText": {"objectId": oid, "text": full}},
                {"updateTextStyle": {"objectId": oid, "style": {"fontFamily": "Arial", "fontSize": {"magnitude": size, "unit": "PT"},
                                                                 "foregroundColor": {"opaqueColor": {"rgbColor": rgb(color)}}},
                                     "fields": "fontFamily,fontSize,foregroundColor"}},
                {"updateParagraphStyle": {"objectId": oid, "style": {"alignment": align, "spaceBelow": {"magnitude": spacing_after, "unit": "PT"}},
                                          "fields": "alignment,spaceBelow"}},
                {"updateShapeProperties": {"objectId": oid, "shapeProperties": {"contentAlignment": valign}, "fields": "contentAlignment"}}]
    start = 0
    for piece, style in runs:
        end = start + len(piece)
        fields, payload = [], {}
        if style.get("bold"):
            payload["bold"] = True
            fields.append("bold")
        if style.get("italic"):
            payload["italic"] = True
            fields.append("italic")
        if style.get("color"):
            payload["foregroundColor"] = {"opaqueColor": {"rgbColor": rgb(style["color"])}}
            fields.append("foregroundColor")
        if style.get("size"):
            payload["fontSize"] = {"magnitude": style["size"], "unit": "PT"}
            fields.append("fontSize")
        if style.get("font"):
            payload["fontFamily"] = style["font"]
            fields.append("fontFamily")
        if fields and end > start:
            requests.append({"updateTextStyle": {"objectId": oid, "textRange": {"type": "FIXED_RANGE", "startIndex": start, "endIndex": end},
                                                 "style": payload, "fields": ",".join(fields)}})
        start = end
    if bullets:
        requests.append({"createParagraphBullets": {"objectId": oid, "textRange": {"type": "ALL"}, "bulletPreset": "BULLET_DISC_CIRCLE_SQUARE"}})
    return requests


def card(page, oid, x, y, w, h):
    return rect(page, oid, x, y, w, h)


def card_title(page, oid, x, y, w, label):
    return text(page, oid, x, y, w, 0.3, label, size=12, align="CENTER", runs_bold=True) if False else \
        text(page, oid, x, y, w, 0.3, [[label, {"bold": True}]], size=12, align="CENTER")


def key_finding(page, oid, body, y=4.62, h=0.6):
    return rect(page, oid + "_band", 0.5, y, 9, h, fill=RED, line=RED) + \
        text(page, oid, 0.65, y, 8.7, h, [["KEY FINDING   ", {"bold": True}], [body, {}]], size=11, color="FFFFFF", valign="MIDDLE")


def source(page, oid, body, y=4.36):
    return text(page, oid, 0.5, y, 9, 0.22, body, size=8, color="8A8A8A")


def stat(page, oid, x, y, w, big, label, color=RED):
    return text(page, oid + "_big", x, y, w, 0.5, [[big, {"bold": True}]], size=26, color=color) + \
        text(page, oid + "_label", x, y + 0.5, w, 0.5, label, size=10, color=MUTED)


def placeholder(page, oid, x, y, w, h, figure):
    """Gray box standing in for a chart image until it can be inserted."""
    return rect(page, oid, x, y, w, h, fill="F7F7F7", line="CCCCCC") + \
        text(page, oid + "_label", x, y + h / 2 - 0.2, w, 0.4, f"[chart: {figure}]", size=10, color="999999", align="CENTER")


def new_content_slide(new_id, insertion_index, num, title, subtitle, template="p16"):
    """Duplicate a content slide for its header formatting, move it, set num/title/subtitle, and return the
    ids of the copied body elements that must be deleted."""
    page = slides.get(presentationId=PID).execute()
    template_slide = next(s for s in page["slides"] if s["objectId"] == template)
    mapping = {template: new_id, f"{template}_i2": f"{new_id}_num", f"{template}_i3": f"{new_id}_title", f"{template}_i4": f"{new_id}_sub"}
    slides.batchUpdate(presentationId=PID, body={"requests": [{"duplicateObject": {"objectId": template, "objectIds": mapping}}]}).execute()
    page = slides.get(presentationId=PID).execute()
    new_slide = next(s for s in page["slides"] if s["objectId"] == new_id)
    keep = [f"{new_id}_num", f"{new_id}_title", f"{new_id}_sub"]
    requests = [{"deleteObject": {"objectId": e["objectId"]}} for e in new_slide.get("pageElements", []) if e["objectId"] not in keep]
    requests.append({"updateSlidesPosition": {"slideObjectIds": [new_id], "insertionIndex": insertion_index}})
    for oid, value in [[f"{new_id}_num", num], [f"{new_id}_title", title], [f"{new_id}_sub", subtitle]]:
        old_length = len("".join(r.get("textRun", {}).get("content", "") for r in
                                 next(e for e in new_slide["pageElements"] if e["objectId"] == oid)["shape"]["text"]["textElements"]).rstrip("\n"))
        requests.append({"insertText": {"objectId": oid, "text": value, "insertionIndex": 0}})
        if old_length:
            requests.append({"deleteText": {"objectId": oid, "textRange": {"type": "FIXED_RANGE", "startIndex": len(value), "endIndex": len(value) + old_length}}})
    slides.batchUpdate(presentationId=PID, body={"requests": requests}).execute()
    notes_id = new_slide["slideProperties"]["notesPage"]["notesProperties"]["speakerNotesObjectId"]
    return notes_id


def set_notes(slide_id, body):
    page = slides.get(presentationId=PID).execute()
    the_slide = next(s for s in page["slides"] if s["objectId"] == slide_id)
    notes_id = the_slide["slideProperties"]["notesPage"]["notesProperties"]["speakerNotesObjectId"]
    notes_shape = next((e for e in the_slide["slideProperties"]["notesPage"].get("pageElements", []) if e["objectId"] == notes_id), None)
    has_text = notes_shape is not None and any(r.get("textRun", {}).get("content", "").strip() for r in notes_shape.get("shape", {}).get("text", {}).get("textElements", []))
    requests = []
    if has_text:
        requests.append({"deleteText": {"objectId": notes_id, "textRange": {"type": "ALL"}}})
    requests.append({"insertText": {"objectId": notes_id, "text": body}})
    slides.batchUpdate(presentationId=PID, body={"requests": requests}).execute()


def run(requests):
    if requests:
        slides.batchUpdate(presentationId=PID, body={"requests": requests}).execute()
