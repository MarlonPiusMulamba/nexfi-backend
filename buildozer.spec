[app]
title = X Clone
package.name = xclone
package.domain = org.example

source.dir = .
source.include_exts = py,png,jpg,kv,atlas,html,css,js
source.exclude_dirs = tests, bin, venv, .git, .idea
source.exclude_patterns = *.pyc, *.pyo

version = 0.1
requirements = python3,flask==2.3.3,pywebview==4.1,pymongo==4.6.0

orientation = portrait
icon.filename = %(source.dir)s/icon.png
android.permissions = INTERNET
android.api = 33
android.minapi = 21
android.ndk = 25b
android.ndk_path = C:\Users\.py\Downloads\android-ndk-r27d-windows
android.sdk_path = C:\Users\.py\Downloads\platform-tools-latest-windows (1)\platform-tools
android.entrypoint = org.renpy.android.PythonActivity
android.archs = arm64-v8a, armeabi-v7a

[buildozer]
log_level = 2
warn_on_root = 1