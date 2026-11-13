# AnRainStudio ROM 发布站

基于 Flask + SQLite 的个人发包博客。首页展示个人联系方式与工作状态，访客先选机型，再选类原生、官改或移植，进入具体文章查看下载和刷机工具。后台可管理工作状态和文章；捐赠入口可逐篇开关，点击后弹窗显示图片。

主页的信息结构和动效节奏参考 [imsyy/home](https://github.com/imsyy/home)，视觉配色与玻璃发光效果结合站长原有页面重新设计。主页时钟显示访客设备的本地时间。

打开或刷新主页时显示开屏动画，开屏结束后自动显示捐赠弹窗。开屏改编自 imsyy/home 的 `Loading.vue`，原作者及 MIT 许可见 `LICENSE-imsyy.txt`。开启捐赠的文章在进入后自动弹窗，如需先确认刷机须知，则按顺序显示。用户可在系统中开启“减少动态效果”以跳过开屏及动画。

## 本地启动（Windows PowerShell）

在本目录打开终端，执行：

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
flask --app app set-admin
python app.py
```

设置密码时输入至少 12 个字符，输入过程不会显示字符。打开 http://127.0.0.1:5000/；后台入口不在页面上显示，请直接访问 http://127.0.0.1:5000/AnPHadmin 。重设密码可再次执行 `flask --app app set-admin`。如果 PowerShell 的执行策略阻止激活，可以直接使用 `.\.venv\Scripts\python.exe -m pip install -r requirements.txt`、`.\.venv\Scripts\python.exe -m flask --app app set-admin` 和 `.\.venv\Scripts\python.exe app.py`，无需激活。

首次运行自动创建 `data/blog.sqlite3`、会话密钥以及初始文章。数据保存在 `data/`；更新程序时请保留并定期备份整个目录。`ANRAIN_DATA_DIR` 环境变量可改变数据目录。初始文章中未给出年份的日期暂按 2026 年排列，Flyme 和 ColorApp 的日期也仅用于初始排序；请在后台按实际发布日期核对修改。初始数据只在数据库第一次建立时导入，以免覆盖后续修改。

## 上线说明

`python app.py` 是仅绑定本机的开发服务器。公开部署时，请在服务器使用正式 WSGI 服务（例如 Linux 上的 Gunicorn）和 HTTPS 反向代理，并对 `/AnPHadmin/login` 配置登录速率限制。隐藏后台入口不能代替密码保护。设置 `COOKIE_SECURE=1`，并将 `ANRAIN_DATA_DIR` 指向持久化且不向公网暴露的目录。确保数据目录和密钥仅服务器账户可读写。请先备份数据再迁移或更新。

外部下载链接、线刷工具和捐赠图片由站长提供，发布前请自行核对其可用性；本项目不托管 ROM 文件。捐赠图保留原图，建议用另一台设备实际扫码确认清晰度。

Flyme 和 Nothing OS 的 C.701 要求已记录在对应帖子中，Android 16 公告也提供 C.701 链接。C.500 的适用 ROM 尚未提供，文章中将其作为待确认的参考链接，不代表适用于该文章的 ROM。

## GitHub Pages 备用下载页

GitHub Actions 从 `seed.py` 生成独立的[静态备用下载页](https://anrainstu.github.io/anrain-rom-blog/)，即使主服务器离线仍可打开下载链接。备用页不运行 Flask、数据库或管理后台，快照不会自动包含主服务器后台新建或修改的内容。更新备用链接时请修改仓库里的 `seed.py` 并推送到 main，Actions 会重新发布。可在本地执行 `python build_static.py site` 生成备用页。
