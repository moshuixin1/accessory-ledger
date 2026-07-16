饰品记账 - 部署到云端
==========================

识图记账工具，拍照识别饰品价格、管理商品、记录销售。

部署到 Render（免费）
--------------------------------------

1. 在 GitHub 创建一个仓库

   https://github.com/new

2. 把代码推上去

   cd 项目目录
   git init
   git add .
   git commit -m "饰品记账"
   git branch -M main
   git remote add origin https://github.com/你的用户名/仓库名.git
   git push -u origin main

3. 在 Render 创建 Web Service

   - 打开 https://dashboard.render.com 注册/登录
   - 点击 "New +" → "Web Service"
   - 连接你的 GitHub 仓库
   - 填写以下信息：
     * Name: accessory-ledger（任意）
     * Region: Singapore（亚洲速度最快）
     * Branch: main
     * Runtime: Python 3
     * Build Command: pip install -r requirements.txt
     * Start Command: gunicorn app:app --bind 0.0.0.0:$PORT
     * Instance Type: Free
   - 点击 "Create Web Service"

4. 等几分钟部署完成

   Render 会自动构建和部署。完成后会给你一个网址，比如：
   https://accessory-ledger.onrender.com

5. 手机打开这个网址就能用了

   添加到手机桌面（PWA 支持），像 App 一样使用。

注意事项
--------

- 免费版服务器 15 分钟无人访问会自动休眠，醒来需 30 秒左右
- 图片和销售数据与服务器共存亡，建议定期备份 data/ 文件夹
- 如果图片较多，建议用 paid plan（$7/月）享受持久化存储

本地运行
--------

python app.py
然后访问 http://127.0.0.1:5000
