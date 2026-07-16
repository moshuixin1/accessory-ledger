import os
import uuid
from datetime import date, timedelta

from flask import Flask, request, jsonify, send_from_directory, render_template
from werkzeug.utils import secure_filename

from database import (init_db, add_item, update_item, delete_item,
                       get_all_items, get_item, search_items,
                       get_categories, add_category,
                       record_sale, get_sales, get_today_summary,
                       get_sales_range, update_item_image)
from image_match import ImageMatcher, make_thumbnail

app = Flask(__name__)

# Ensure directories exist
os.makedirs("catalog", exist_ok=True)
os.makedirs("sales", exist_ok=True)

ALLOWED_EXT = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}

# -- Global image matcher (initialised after DB is ready) --
_matcher = ImageMatcher()


# ---------------------------------------------------------------------------
#  Helpers
# ---------------------------------------------------------------------------

def _save_upload(file, folder="catalog"):
    ext = os.path.splitext(file.filename.lower())[1]
    if ext not in ALLOWED_EXT:
        ext = ".jpg"
    name = f"{uuid.uuid4().hex}{ext}"
    path = os.path.join(folder, name)
    file.save(path)
    return path


def _rebuild_matcher():
    items = get_all_items()
    valid = [(i["id"], i["image_path"]) for i in items
             if i["image_path"] and os.path.isfile(i["image_path"])]
    _matcher.rebuild(valid)


# ---------------------------------------------------------------------------
#  Pages
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return render_template("index.html")


# ---------------------------------------------------------------------------
#  Item CRUD
# ---------------------------------------------------------------------------

@app.route("/api/items", methods=["GET"])
def api_list_items():
    q = request.args.get("q", "")
    items = search_items(q) if q else get_all_items()
    return jsonify(items)


@app.route("/api/items", methods=["POST"])
def api_add_item():
    name = request.form.get("name", "").strip()
    price = request.form.get("price", type=float)
    category_id = request.form.get("category_id", type=int)
    note = request.form.get("note", "")
    stock = request.form.get("stock", 1, type=int)
    if not name or price is None:
        return jsonify({"error": "名称和价格不能为空"}), 400

    image_path = thumb_path = ""
    file = request.files.get("image")
    if file and file.filename:
        image_path = _save_upload(file, "catalog")
        thumb_name = "thumb_" + os.path.basename(image_path)
        thumb_path = os.path.join("catalog", thumb_name)
        make_thumbnail(os.path.join(app.root_path, image_path),
                       os.path.join(app.root_path, thumb_path))

    item_id = add_item(name, price, category_id, image_path, thumb_path, note, stock)
    _rebuild_matcher()
    return jsonify({"id": item_id}), 201


@app.route("/api/items/<int:item_id>", methods=["PUT"])
def api_update_item(item_id):
    name = request.form.get("name", "").strip()
    price = request.form.get("price", type=float)
    category_id = request.form.get("category_id", type=int)
    note = request.form.get("note", "")
    stock = request.form.get("stock", 1, type=int)
    if not name or price is None:
        return jsonify({"error": "名称和价格不能为空"}), 400

    update_item(item_id, name, price, category_id, note, stock)

    file = request.files.get("image")
    if file and file.filename:
        image_path = _save_upload(file, "catalog")
        thumb_name = "thumb_" + os.path.basename(image_path)
        thumb_path = os.path.join("catalog", thumb_name)
        make_thumbnail(os.path.join(app.root_path, image_path),
                       os.path.join(app.root_path, thumb_path))
        update_item_image(item_id, image_path, thumb_path)
        _rebuild_matcher()

    return jsonify({"ok": True})


@app.route("/api/items/<int:item_id>", methods=["DELETE"])
def api_delete_item(item_id):
    paths = delete_item(item_id)
    if paths:
        for p in [paths["image_path"], paths["thumb_path"]]:
            if p and os.path.isfile(p):
                os.remove(p)
    _rebuild_matcher()
    return jsonify({"ok": True})


# ---------------------------------------------------------------------------
#  Categories
# ---------------------------------------------------------------------------

@app.route("/api/categories", methods=["GET"])
def api_list_categories():
    return jsonify(get_categories())


@app.route("/api/categories", methods=["POST"])
def api_add_category():
    name = request.json.get("name", "").strip()
    if not name:
        return jsonify({"error": "分类名称不能为空"}), 400
    new_id = add_category(name)
    return jsonify({"id": new_id}), 201


# ---------------------------------------------------------------------------
#  Image matching (the core "识图" feature)
# ---------------------------------------------------------------------------

@app.route("/api/match", methods=["POST"])
def api_match():
    """Upload a sales photo, find matching catalog items."""
    file = request.files.get("image")
    if not file or not file.filename:
        return jsonify({"error": "请上传图片"}), 400

    img_path = _save_upload(file, "sales")

    results = _matcher.match(os.path.join(app.root_path, img_path), top_k=6)

    matched_items = []
    for item_id, score in results:
        item = get_item(item_id)
        if item:
            item["match_score"] = score
            matched_items.append(item)

    return jsonify({"image": img_path, "matches": matched_items})


# ---------------------------------------------------------------------------
#  Sales
# ---------------------------------------------------------------------------

@app.route("/api/sales", methods=["POST"])
def api_record_sale():
    data = request.json
    item_id = data.get("item_id")
    item_name = data.get("item_name", "")
    price = data.get("price", 0, type=float)
    quantity = data.get("quantity", 1, type=int)
    payment = data.get("payment_method", "现金")
    note = data.get("note", "")

    if not item_id or not item_name:
        return jsonify({"error": "商品ID和名称不能为空"}), 400

    sale_id = record_sale(item_id, item_name, price, quantity, payment, note)
    return jsonify({"id": sale_id}), 201


@app.route("/api/sales/today", methods=["GET"])
def api_today_sales():
    summary = get_today_summary()
    sales = get_sales(sale_date=date.today().isoformat())
    return jsonify({"summary": summary, "sales": sales})


@app.route("/api/sales/range", methods=["GET"])
def api_sales_range():
    start = request.args.get("start", (date.today() - timedelta(days=7)).isoformat())
    end = request.args.get("end", date.today().isoformat())
    sales = get_sales_range(start, end)
    total = round(sum(s["price"] * s["quantity"] for s in sales), 2)
    return jsonify({"sales": sales, "total": total, "start": start, "end": end})


@app.route("/api/sales/recent", methods=["GET"])
def api_recent_sales():
    return jsonify(get_sales(limit=50))


# ---------------------------------------------------------------------------
#  Static files (images)
# ---------------------------------------------------------------------------

@app.route("/uploads/<path:filename>")
def uploaded_file(filename):
    directory = os.path.dirname(filename)
    basename = os.path.basename(filename)
    return send_from_directory(os.path.join(app.root_path, directory), basename)


# ---------------------------------------------------------------------------
#  Start-up
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    init_db()
    _rebuild_matcher()
    app.run(host="0.0.0.0", port=5000, debug=True)
import os
import uuid
from datetime import date, timedelta

from flask import Flask, request, jsonify, send_from_directory, render_template
from werkzeug.utils import secure_filename

from database import (init_db, add_item, update_item, delete_item,
                       get_all_items, get_item, search_items,
                       get_categories, add_category,
                       record_sale, get_sales, get_today_summary,
                       get_sales_range, update_item_image)
from image_match import ImageMatcher, make_thumbnail

app = Flask(__name__)

# Ensure directories exist
os.makedirs("catalog", exist_ok=True)
os.makedirs("sales", exist_ok=True)

ALLOWED_EXT = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}

# -- Global image matcher (initialised after DB is ready) --
_matcher = ImageMatcher()


# ---------------------------------------------------------------------------
#  Helpers
# ---------------------------------------------------------------------------

def _save_upload(file, folder="catalog"):
    ext = os.path.splitext(file.filename.lower())[1]
    if ext not in ALLOWED_EXT:
        ext = ".jpg"
    name = f"{uuid.uuid4().hex}{ext}"
    path = os.path.join(folder, name)
    file.save(path)
    return path


def _rebuild_matcher():
    items = get_all_items()
    valid = [(i["id"], i["image_path"]) for i in items
             if i["image_path"] and os.path.isfile(i["image_path"])]
    _matcher.rebuild(valid)


# ---------------------------------------------------------------------------
#  Pages
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return render_template("index.html")


# ---------------------------------------------------------------------------
#  Item CRUD
# ---------------------------------------------------------------------------

@app.route("/api/items", methods=["GET"])
def api_list_items():
    q = request.args.get("q", "")
    items = search_items(q) if q else get_all_items()
    return jsonify(items)


@app.route("/api/items", methods=["POST"])
def api_add_item():
    name = request.form.get("name", "").strip()
    price = request.form.get("price", type=float)
    category_id = request.form.get("category_id", type=int)
    note = request.form.get("note", "")
    stock = request.form.get("stock", 1, type=int)
    if not name or price is None:
        return jsonify({"error": "名称和价格不能为空"}), 400

    image_path = thumb_path = ""
    file = request.files.get("image")
    if file and file.filename:
        image_path = _save_upload(file, "catalog")
        thumb_name = "thumb_" + os.path.basename(image_path)
        thumb_path = os.path.join("catalog", thumb_name)
        make_thumbnail(os.path.join(app.root_path, image_path),
                       os.path.join(app.root_path, thumb_path))

    item_id = add_item(name, price, category_id, image_path, thumb_path, note, stock)
    _rebuild_matcher()
    return jsonify({"id": item_id}), 201


@app.route("/api/items/<int:item_id>", methods=["PUT"])
def api_update_item(item_id):
    name = request.form.get("name", "").strip()
    price = request.form.get("price", type=float)
    category_id = request.form.get("category_id", type=int)
    note = request.form.get("note", "")
    stock = request.form.get("stock", 1, type=int)
    if not name or price is None:
        return jsonify({"error": "名称和价格不能为空"}), 400

    update_item(item_id, name, price, category_id, note, stock)

    file = request.files.get("image")
    if file and file.filename:
        image_path = _save_upload(file, "catalog")
        thumb_name = "thumb_" + os.path.basename(image_path)
        thumb_path = os.path.join("catalog", thumb_name)
        make_thumbnail(os.path.join(app.root_path, image_path),
                       os.path.join(app.root_path, thumb_path))
        update_item_image(item_id, image_path, thumb_path)
        _rebuild_matcher()

    return jsonify({"ok": True})


@app.route("/api/items/<int:item_id>", methods=["DELETE"])
def api_delete_item(item_id):
    paths = delete_item(item_id)
    if paths:
        for p in [paths["image_path"], paths["thumb_path"]]:
            if p and os.path.isfile(p):
                os.remove(p)
    _rebuild_matcher()
    return jsonify({"ok": True})


# ---------------------------------------------------------------------------
#  Categories
# ---------------------------------------------------------------------------

@app.route("/api/categories", methods=["GET"])
def api_list_categories():
    return jsonify(get_categories())


@app.route("/api/categories", methods=["POST"])
def api_add_category():
    name = request.json.get("name", "").strip()
    if not name:
        return jsonify({"error": "分类名称不能为空"}), 400
    new_id = add_category(name)
    return jsonify({"id": new_id}), 201


# ---------------------------------------------------------------------------
#  Image matching (the core "识图" feature)
# ---------------------------------------------------------------------------

@app.route("/api/match", methods=["POST"])
def api_match():
    """Upload a sales photo, find matching catalog items."""
    file = request.files.get("image")
    if not file or not file.filename:
        return jsonify({"error": "请上传图片"}), 400

    img_path = _save_upload(file, "sales")

    results = _matcher.match(os.path.join(app.root_path, img_path), top_k=6)

    matched_items = []
    for item_id, score in results:
        item = get_item(item_id)
        if item:
            item["match_score"] = score
            matched_items.append(item)

    return jsonify({"image": img_path, "matches": matched_items})


# ---------------------------------------------------------------------------
#  Sales
# ---------------------------------------------------------------------------

@app.route("/api/sales", methods=["POST"])
def api_record_sale():
    data = request.json
    item_id = data.get("item_id")
    item_name = data.get("item_name", "")
    price = data.get("price", 0, type=float)
    quantity = data.get("quantity", 1, type=int)
    payment = data.get("payment_method", "现金")
    note = data.get("note", "")

    if not item_id or not item_name:
        return jsonify({"error": "商品ID和名称不能为空"}), 400

    sale_id = record_sale(item_id, item_name, price, quantity, payment, note)
    return jsonify({"id": sale_id}), 201


@app.route("/api/sales/today", methods=["GET"])
def api_today_sales():
    summary = get_today_summary()
    sales = get_sales(sale_date=date.today().isoformat())
    return jsonify({"summary": summary, "sales": sales})


@app.route("/api/sales/range", methods=["GET"])
def api_sales_range():
    start = request.args.get("start", (date.today() - timedelta(days=7)).isoformat())
    end = request.args.get("end", date.today().isoformat())
    sales = get_sales_range(start, end)
    total = round(sum(s["price"] * s["quantity"] for s in sales), 2)
    return jsonify({"sales": sales, "total": total, "start": start, "end": end})


@app.route("/api/sales/recent", methods=["GET"])
def api_recent_sales():
    return jsonify(get_sales(limit=50))


# ---------------------------------------------------------------------------
#  Static files (images)
# ---------------------------------------------------------------------------

@app.route("/uploads/<path:filename>")
def uploaded_file(filename):
    directory = os.path.dirname(filename)
    basename = os.path.basename(filename)
    return send_from_directory(os.path.join(app.root_path, directory), basename)


# ---------------------------------------------------------------------------
#  Start-up
# ---------------------------------------------------------------------------
@app.route("/health")
def health():
    return jsonify({"status": "ok"})


# ---------------------------------------------------------------------------
#  App startup (runs on both local `python app.py` and gunicorn import)
# ---------------------------------------------------------------------------

# These must execute at module level so gunicorn workers are ready
init_db()
_rebuild_matcher()

PORT = int(os.environ.get("PORT", "5000"))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT, debug=False)
