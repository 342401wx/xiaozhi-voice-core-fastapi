from __future__ import annotations

import base64
import time
import wave
import json
import os
import mimetypes
import shutil
import uuid
import html
import hmac
import hashlib
import secrets
import sqlite3
import string
from datetime import datetime
from pathlib import Path
from typing import Any, Optional
from urllib import error, request

import gradio as gr
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles


PROJECT_ROOT = Path(__file__).resolve().parent
SERVICES_DIR = PROJECT_ROOT / "services"
ASSETS_DIR = PROJECT_ROOT / "assets"
VOICE_CORE_DIR = SERVICES_DIR / "voice_core"
WEB_STATIC_DIR = ASSETS_DIR / "web_static"
DIGITAL_HUMAN_DIR = ASSETS_DIR / "digital_human"


APP_CSS = """
:root {
  --surface: #edf6f2;
  --panel: #ffffff;
  --panel-soft: #f5faf7;
  --ink: #172522;
  --muted: #687a74;
  --line: #d9e7e1;
  --accent: #0e8f70;
  --accent-strong: #087158;
  --danger: #b74747;
  --stage: #fae9ef;
  --stage-deep: #f3c8d6;
}

.gradio-container {
  background:
    radial-gradient(circle at 50% 0%, rgba(14,143,112,.16), transparent 32%),
    linear-gradient(180deg, #fbfdfb 0%, var(--surface) 100%);
  color: var(--ink);
}

.gradio-container .contain {
  max-width: none !important;
}

.app-shell {
  max-width: 1640px;
  margin: 0 auto;
  padding: 10px 14px 18px;
}

.call-topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  min-height: 60px;
  padding: 12px 16px;
  margin-bottom: 12px;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: rgba(255,255,255,.94);
  box-shadow: 0 12px 30px rgba(28, 72, 61, .08);
}

.call-title {
  display: flex;
  align-items: center;
  gap: 10px;
  font-weight: 900;
  font-size: 20px;
  letter-spacing: 0;
}

.call-glyph {
  width: 34px;
  height: 34px;
  border-radius: 50%;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  background: var(--accent);
  font-weight: 900;
  box-shadow: 0 0 0 6px rgba(14,143,112,.12);
}

.call-subline {
  color: var(--muted);
  font-size: 12px;
  margin-top: 2px;
}

.workbench-grid {
  align-items: stretch;
  gap: 12px !important;
}

.rail-card, .stage-card, .right-card {
  border: 1px solid var(--line);
  border-radius: 8px;
  background: rgba(255,255,255,.94);
  box-shadow: 0 16px 40px rgba(28, 72, 61, .08);
  padding: 14px;
}

.stage-card {
  display: flex;
  flex-direction: column;
  justify-content: flex-start;
  background:
    linear-gradient(180deg, rgba(255,255,255,.96) 0%, rgba(255,255,255,.88) 42%),
    var(--stage);
}

.rail-title {
  margin: 0 0 12px;
  font-size: 16px;
  font-weight: 900;
  color: var(--ink);
}

.live2d-section {
  margin-top: 0;
  margin-bottom: 0;
  border-radius: 8px;
  overflow: hidden;
  border: 1px solid rgba(204, 106, 135, .25);
  box-shadow: inset 0 1px 0 rgba(255,255,255,.8), 0 14px 34px rgba(120, 64, 85, .13);
  background:
    linear-gradient(180deg, rgba(255,255,255,.28), rgba(255,255,255,0) 48%),
    radial-gradient(circle at 50% 18%, #ffffff 0%, var(--stage) 34%, var(--stage-deep) 100%);
}

.live2d-section iframe {
  height: 620px !important;
  display: block;
}

.role-drawer {
  margin-bottom: 6px;
  border-radius: 8px !important;
  overflow: hidden !important;
  transition: box-shadow .24s ease, border-color .24s ease, background-color .24s ease;
}

.role-drawer > .label-wrap,
.role-drawer button {
  font-weight: 800 !important;
}

.role-drawer > button.label-wrap {
  min-height: 42px !important;
  border-radius: 8px !important;
  transition: background-color .18s ease, color .18s ease;
}

.role-drawer > button.label-wrap:hover {
  background: rgba(14,143,112,.06) !important;
}

.role-drawer > button.label-wrap .icon {
  transition: transform .28s cubic-bezier(.16, 1, .3, 1) !important;
}

.role-drawer fieldset .wrap {
  gap: 8px !important;
}

.role-drawer fieldset label {
  border-radius: 8px !important;
}

.role-drawer [hidden],
.role-drawer [aria-hidden="true"] {
  display: none !important;
}

.role-drawer-shell {
  margin-bottom: 8px;
}

.role-drawer-shell details {
  border: 1px solid rgba(14,143,112,.18);
  border-radius: 8px;
  background: #fff;
  overflow: hidden;
}

.role-drawer-shell summary,
.role-drawer-toggle {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  min-height: 44px;
  padding: 0 12px;
  border: 1px solid rgba(14,143,112,.18);
  border-radius: 8px;
  background: #fff;
  cursor: pointer;
  color: var(--ink);
  font-weight: 900;
  text-align: left;
  list-style: none;
}

.role-drawer-shell summary::-webkit-details-marker {
  display: none;
}

.role-drawer-shell summary::after,
.role-drawer-toggle::after {
  content: "▾";
  color: var(--accent-strong);
  font-size: 12px;
  transform: rotate(-90deg);
  transition: transform .18s ease;
}

.role-drawer-shell details[open] summary::after,
.role-drawer-toggle[aria-expanded="true"]::after {
  transform: rotate(0deg);
}

.role-toolbar {
  display: grid !important;
  grid-template-columns: 1fr;
  gap: 12px !important;
  align-items: stretch;
  margin: -2px 0 10px;
  padding: 12px;
  border: 1px solid rgba(14,143,112,.18);
  border-top: 0;
  border-radius: 0 0 8px 8px;
  background: rgba(255,255,255,.92);
  box-shadow: 0 12px 28px rgba(28,72,61,.08);
}

.role-toolbar:not(.role-toolbar-open) {
  display: none !important;
}

.role-select {
  min-width: 0 !important;
  max-width: none !important;
  width: 100% !important;
}

.mode-segment {
  min-width: 0 !important;
  width: 100% !important;
}

.voice-preview-btn {
  width: 100% !important;
  margin-top: 2px !important;
}

.role-toolbar .form,
.role-toolbar .block {
  margin: 0 !important;
  border: 0 !important;
  background: transparent !important;
  box-shadow: none !important;
}

.role-toolbar > .gap,
.role-toolbar .gap {
  gap: 10px !important;
}

.role-toolbar .form {
  padding: 0 !important;
}

.role-toolbar fieldset {
  min-width: 0 !important;
  width: 100% !important;
  border: 0 !important;
  padding: 0 !important;
  margin: 0 !important;
}

.role-toolbar fieldset legend {
  display: block !important;
  width: 100% !important;
  margin: 0 0 7px !important;
  padding: 0 !important;
  color: var(--muted) !important;
  font-size: 12px !important;
  font-weight: 900 !important;
  line-height: 1.3 !important;
}

.role-toolbar fieldset .wrap {
  display: grid !important;
  grid-template-columns: 1fr !important;
  gap: 8px !important;
}

.role-toolbar fieldset label {
  display: flex !important;
  align-items: center !important;
  justify-content: flex-start !important;
  min-height: 42px !important;
  width: 100% !important;
  margin: 0 !important;
  padding: 8px 10px !important;
  border: 1px solid rgba(14,143,112,.16) !important;
  border-radius: 8px !important;
  background: #fff !important;
  color: var(--ink) !important;
  font-weight: 800 !important;
  white-space: nowrap !important;
  transition: background-color .16s ease, border-color .16s ease, box-shadow .16s ease;
}

.role-toolbar fieldset label:hover {
  border-color: rgba(14,143,112,.35) !important;
  background: rgba(14,143,112,.05) !important;
}

.role-toolbar fieldset label:has(input:checked) {
  border-color: rgba(14,143,112,.70) !important;
  background: rgba(14,143,112,.10) !important;
  box-shadow: inset 3px 0 0 var(--accent-strong) !important;
}

.role-toolbar fieldset input[type="radio"] {
  margin-right: 8px !important;
  accent-color: var(--accent-strong);
}

.role-toolbar button {
  min-height: 40px !important;
  border-radius: 8px !important;
  font-weight: 900 !important;
}

.role-hidden {
  display: none !important;
}

@media (prefers-reduced-motion: reduce) {
  .role-drawer,
  .role-drawer > button.label-wrap,
  .role-drawer > button.label-wrap .icon,
  .role-drawer > button.label-wrap + div {
    animation: none !important;
    transition: none !important;
  }
}

.call-card {
  position: relative;
  overflow: hidden;
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 16px;
  margin-bottom: 12px;
  background:
    linear-gradient(135deg, rgba(255,255,255,.96), rgba(244,250,247,.94)),
    var(--panel);
}

.call-card::after {
  content: "";
  position: absolute;
  inset: auto -28px -44px auto;
  width: 120px;
  height: 120px;
  border-radius: 999px;
  background: rgba(14,143,112,.09);
  pointer-events: none;
}

.call-card-active {
  border-color: rgba(14,143,112,.46);
  background:
    linear-gradient(135deg, rgba(14,143,112,.14), rgba(255,255,255,.96) 62%),
    var(--panel);
}

.call-line {
  display: flex;
  align-items: center;
  gap: 12px;
}

.call-dot {
  width: 13px;
  height: 13px;
  border-radius: 50%;
  background: #a1ada8;
  box-shadow: 0 0 0 6px rgba(161,173,168,.12);
  flex: 0 0 auto;
}

.call-card-active .call-dot {
  background: var(--accent);
  box-shadow: 0 0 0 6px rgba(14,143,112,.15), 0 0 24px rgba(14,143,112,.35);
  animation: callPulse 1.7s ease-in-out infinite;
}

@keyframes callPulse {
  0%, 100% { transform: scale(1); }
  50% { transform: scale(1.22); }
}

.call-line b {
  display: block;
  font-size: 16px;
}

.call-line span {
  display: block;
  color: var(--muted);
  font-size: 12px;
  margin-top: 2px;
}

.dial-number {
  margin-top: 14px;
  padding: 12px;
  border-radius: 8px;
  border: 1px solid var(--line);
  background: #fbfdfc;
  font-weight: 900;
  color: var(--ink);
}

.call-meta {
  margin-top: 8px;
  color: var(--muted);
  font-size: 12px;
}

.call-action-row button {
  min-height: 44px !important;
  border-radius: 8px !important;
  font-weight: 900 !important;
}

#xz-call-toggle button.stop,
#xz-call-toggle .stop button,
#xz-call-toggle button[class*="stop"],
.call-action-row button.stop,
.call-action-row .stop button,
.call-action-row button[class*="stop"] {
  background: #dc2626 !important;
  background-image: none !important;
  border-color: #dc2626 !important;
  color: #fff !important;
  box-shadow: none !important;
}

#xz-call-toggle button.stop:hover,
#xz-call-toggle .stop button:hover,
#xz-call-toggle button[class*="stop"]:hover,
.call-action-row button.stop:hover,
.call-action-row .stop button:hover,
.call-action-row button[class*="stop"]:hover {
  background: #b91c1c !important;
  border-color: #b91c1c !important;
}

button.primary, .primary button {
  background: var(--accent) !important;
  border-color: var(--accent) !important;
  color: #fff !important;
}

button.primary:hover, .primary button:hover {
  background: var(--accent-strong) !important;
}

button.danger, .danger button {
  background: var(--danger) !important;
  border-color: var(--danger) !important;
  color: #fff !important;
}

.status-pill {
  display: inline-flex;
  align-items: center;
  min-height: 28px;
  padding: 3px 10px;
  border-radius: 999px;
  border: 1px solid rgba(14,143,112,.26);
  background: rgba(14,143,112,.08);
  color: var(--accent-strong);
  font-weight: 800;
  font-size: 13px;
}

.metric-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
}

.metric, .check-item {
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 10px;
  background: #fbfcfa;
}

.metric b, .check-item b {
  display: block;
  color: var(--ink);
  font-size: 14px;
}

.metric span, .check-item span {
  color: var(--muted);
  font-size: 11px;
}

.insight-list {
  margin: 0;
  padding-left: 16px;
  color: var(--muted);
  line-height: 1.7;
  font-size: 13px;
}

.insight-list strong {
  color: var(--ink);
}

.check-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
}

.char-card {
  display: flex;
  align-items: center;
  gap: 12px;
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 12px;
  background: linear-gradient(135deg, #fbfcfa 0%, #f3f8f5 100%);
  margin-bottom: 8px;
}

.char-avatar-img {
  width: 52px;
  height: 52px;
  border-radius: 50%;
  object-fit: cover;
  flex-shrink: 0;
  box-shadow: 0 3px 10px rgba(0,0,0,.12);
  border: 2px solid #fff;
}

.char-info {
  flex: 1;
  min-width: 0;
}

.char-name {
  font-size: 15px;
  font-weight: 900;
  color: var(--ink);
  margin-bottom: 2px;
}

.char-tag {
  display: inline-block;
  font-size: 10px;
  font-weight: 800;
  padding: 1px 7px;
  border-radius: 999px;
  background: rgba(14,143,112,.1);
  color: var(--accent-strong);
  margin-left: 6px;
  vertical-align: middle;
}

.char-desc {
  color: var(--muted);
  font-size: 12px;
  line-height: 1.5;
}

.char-meta-row {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 8px;
}

.voice-chip {
  display: inline-flex;
  align-items: center;
  min-height: 26px;
  padding: 3px 9px;
  border-radius: 999px;
  border: 1px solid rgba(14,143,112,.18);
  background: rgba(14,143,112,.08);
  color: var(--accent-strong);
  font-size: 12px;
  font-weight: 800;
}

.user-profile-card {
  display: flex;
  align-items: center;
  gap: 12px;
  margin: 0 0 10px;
  padding: 10px;
  border: 1px solid rgba(14,143,112,.18);
  border-radius: 8px;
  background: #fbfdfc;
}

.current-user-strip {
  display: flex;
  align-items: center;
  gap: 12px;
  margin: 0 0 12px;
  padding: 12px;
  border: 1px solid rgba(14,143,112,.18);
  border-radius: 8px;
  background: linear-gradient(135deg, rgba(251,253,252,.98), rgba(239,249,244,.96));
}

.current-user-strip .user-profile-avatar {
  width: 44px;
  height: 44px;
}

.current-user-strip .user-profile-chips {
  margin-top: 5px;
}

.user-profile-avatar {
  width: 50px;
  height: 50px;
  border-radius: 50%;
  object-fit: cover;
  flex: 0 0 auto;
  border: 2px solid #fff;
  box-shadow: 0 3px 10px rgba(0,0,0,.12);
}

.user-profile-meta {
  min-width: 0;
}

.user-profile-name {
  font-size: 15px;
  font-weight: 900;
  color: var(--ink);
}

.user-profile-sub {
  margin-top: 2px;
  color: var(--muted);
  font-size: 12px;
}

.user-profile-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 7px;
}

.user-profile-chips span {
  min-height: 24px;
  padding: 2px 8px;
  border-radius: 999px;
  background: rgba(14,143,112,.08);
  color: var(--accent-strong);
  font-size: 11px;
  font-weight: 800;
}

.profile-settings {
  margin: 0 0 12px;
  padding: 12px;
  border: 1px solid rgba(14,143,112,.18);
  border-radius: 8px;
  background: rgba(255,255,255,.94);
}

.profile-settings .form,
.profile-settings .block {
  margin: 0 !important;
}

.profile-settings button {
  min-height: 40px !important;
  border-radius: 8px !important;
  font-weight: 900 !important;
}

.profile-status {
  margin: 8px 0 0 !important;
  color: var(--accent-strong) !important;
  font-size: 12px !important;
  font-weight: 800 !important;
}

.right-card {
  min-width: min(560px, 100%) !important;
  min-height: min(920px, calc(100dvh - 112px)) !important;
  display: flex !important;
  flex-direction: column !important;
}

.right-card > .tabs,
.right-card .tabitem,
.right-card [role="tabpanel"] {
  flex: 1 1 auto !important;
  min-height: 0 !important;
}

.main-chatbot,
.main-chatbot > div,
.main-chatbot .wrap {
  min-height: min(900px, calc(100dvh - 176px)) !important;
}

.main-chatbot .chatbot,
.main-chatbot [role="log"] {
  min-height: min(835px, calc(100dvh - 242px)) !important;
  max-height: min(835px, calc(100dvh - 242px)) !important;
  overflow-y: auto !important;
}

.main-chatbot .message-wrap {
  min-height: 0 !important;
  margin: 0 0 12px !important;
  padding: 0 !important;
}

.main-chatbot .message-row {
  gap: 16px !important;
  align-items: flex-start !important;
}

.main-chatbot .avatar-container {
  width: 80px !important;
  height: 80px !important;
  min-width: 80px !important;
  min-height: 80px !important;
  border-radius: 50% !important;
  border: 2px solid #fff !important;
  box-shadow: 0 8px 20px rgba(23,37,34,.16) !important;
  overflow: hidden !important;
}

.main-chatbot .avatar-container img,
.main-chatbot img.avatar-image {
  width: 80px !important;
  height: 80px !important;
  object-fit: cover !important;
}

.main-chatbot .message-row.with_avatar .flex-wrap {
  width: calc(100% - 96px) !important;
}

.main-chatbot [data-testid="bot"],
.main-chatbot [data-testid="user"] {
  margin-bottom: 12px !important;
}

.voice-action-row {
  align-items: center;
}

.reply-guard-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  min-height: 38px;
  margin: 8px 0 10px;
  padding: 8px 10px;
  border: 1px solid rgba(14,143,112,.18);
  border-radius: 8px;
  background: #fbfdfc;
  color: var(--muted);
  font-size: 12px;
}

.reply-guard-card strong {
  color: var(--ink);
  font-weight: 900;
}

.reply-guard-status {
  min-width: 74px;
  text-align: center;
  padding: 2px 8px;
  border-radius: 999px;
  background: rgba(14,143,112,.1);
  color: var(--accent-strong);
  font-weight: 900;
}

.skip-voice button {
  min-height: 44px !important;
  border-radius: 8px !important;
  font-weight: 900 !important;
}

.hidden-call-bridge {
  position: absolute !important;
  left: -10000px !important;
  top: auto !important;
  width: 1px !important;
  height: 1px !important;
  overflow: hidden !important;
  opacity: 0 !important;
}

.mic-meter-card {
  margin: 8px 0 12px;
  padding: 10px 11px;
  border: 1px solid rgba(14,143,112,.18);
  border-radius: 8px;
  background: linear-gradient(180deg, rgba(245,250,247,.98), rgba(255,255,255,.94));
}

.mic-meter-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 8px;
}

.mic-meter-title {
  font-size: 12px;
  font-weight: 900;
  color: var(--ink);
}

.mic-meter-status {
  min-width: 58px;
  text-align: center;
  padding: 2px 8px;
  border-radius: 999px;
  background: rgba(14,143,112,.1);
  color: var(--accent-strong);
  font-size: 11px;
  font-weight: 800;
}

.mic-meter-track {
  position: relative;
  height: 12px;
  overflow: hidden;
  border-radius: 999px;
  background: #e6eee9;
  box-shadow: inset 0 1px 2px rgba(23,37,34,.12);
}

.mic-meter-fill {
  width: 0%;
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, #12a67f 0%, #61c46b 58%, #f2b94b 82%, #d94d4d 100%);
  transition: width .08s linear;
}

.mic-meter-bottom {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-top: 7px;
}

.mic-meter-value {
  font-size: 11px;
  font-weight: 800;
  color: var(--muted);
  font-variant-numeric: tabular-nums;
}

.mic-meter-button {
  min-height: 30px;
  padding: 4px 10px;
  border: 1px solid rgba(14,143,112,.24);
  border-radius: 8px;
  background: #fff;
  color: var(--accent-strong);
  font-size: 12px;
  font-weight: 900;
  cursor: pointer;
}

.mic-meter-button:hover {
  background: rgba(14,143,112,.08);
}

input[type="text"], textarea, .wrap, .block {
  border-radius: 8px !important;
}

textarea:focus, input:focus {
  border-color: rgba(14,143,112,.58) !important;
  box-shadow: 0 0 0 3px rgba(14,143,112,.11) !important;
}

@media (max-width: 1180px) {
  .workbench-grid {
    flex-wrap: wrap;
  }
  .live2d-section iframe {
    height: 580px !important;
  }
}

@media (max-width: 980px) {
  .call-topbar { align-items: flex-start; flex-direction: column; }
  .metric-grid, .check-grid { grid-template-columns: 1fr; }
  .live2d-section iframe { height: 560px !important; }
  .right-card { min-height: 760px !important; }
  .main-chatbot,
  .main-chatbot > div,
  .main-chatbot .wrap { min-height: 720px !important; }
  .main-chatbot .chatbot,
  .main-chatbot [role="log"] {
    min-height: 660px !important;
    max-height: 660px !important;
    overflow-y: auto !important;
  }
  .main-chatbot .message-wrap { min-height: 0 !important; margin-bottom: 12px !important; }
}
"""

VOICE_PREVIEW_JS = """
() => {
  window.xzFrontendVersion = "xiaozhi-frame-v4-boot-20260706";
  const pickVoice = (voices, character) => {
    const preferred = voices.filter((voice) => /zh|cmn|Chinese|中文/i.test(`${voice.lang} ${voice.name}`));
    const pool = preferred.length ? preferred : voices;
    const femaleHints = /Xiaoxiao|Xiaoyi|Xiaomeng|HsiaoYu|female|girl|女|晓|小/i;
    if (character === "胡桃小朋友") {
      return pool.find((voice) => femaleHints.test(voice.name)) || pool[0] || null;
    }
    if (character === "名取同学") {
      return pool.find((voice) => /WanLung|Hong Kong|香港|HK|雲龍|云龙|Yunjian|云健|male|男/i.test(`${voice.lang} ${voice.name}`)) || pool[0] || null;
    }
    return pool.find((voice) => femaleHints.test(voice.name)) || pool[0] || null;
  };

  const plainText = (value) => String(value || "")
    .replace(/【[^】]+】/g, "")
    .replace(/\[[^\]]+\]/g, "")
    .replace(/\([^)]*\)/g, "")
    .replace(/[*_`#>|-]/g, "")
    .replace(/\s+/g, " ")
    .trim();

  const getLastAssistantText = (messages) => {
    if (!Array.isArray(messages)) return "";
    for (let index = messages.length - 1; index >= 0; index -= 1) {
      const item = messages[index] || {};
      if (item.role === "assistant") return plainText(item.content);
    }
    return "";
  };

  window.xzSpeakText = (text, character = "") => {
    if (!("speechSynthesis" in window) || !text) return;
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = character === "名取同学" ? "zh-HK" : "zh-CN";
    utterance.volume = 0.92;
    utterance.rate = character === "胡桃小朋友" ? 1.26 : character === "名取同学" ? 0.92 : 1.02;
    utterance.pitch = character === "胡桃小朋友" ? 1.72 : character === "名取同学" ? 0.24 : 1.08;
    const voices = window.speechSynthesis.getVoices();
    const selectedVoice = pickVoice(voices, character);
    if (selectedVoice) utterance.voice = selectedVoice;
    utterance.onstart = () => {
      if (window.xzEnterReplyGuard) window.xzEnterReplyGuard("浏览器语音播放中", { playing: true });
    };
    utterance.onend = () => {
      if (window.xzExitReplyGuard) window.xzExitReplyGuard(900);
    };
    utterance.onerror = () => {
      if (window.xzExitReplyGuard) window.xzExitReplyGuard(500);
    };
    window.speechSynthesis.speak(utterance);
  };

  window.xzSpeakLastAssistant = (messages, character = "") => {
    const text = getLastAssistantText(messages);
    if (text) window.xzSpeakText(text, character);
  };

  if ("speechSynthesis" in window) {
    window.speechSynthesis.onvoiceschanged = () => window.speechSynthesis.getVoices();
  }

  const initMicMeter = () => {
    const root = document.getElementById("xz-mic-meter");
    if (!root || root.dataset.ready === "1") return;
    root.dataset.ready = "1";

    const fill = root.querySelector("#xz-mic-meter-fill");
    const status = root.querySelector("#xz-mic-meter-status");
    const value = root.querySelector("#xz-mic-meter-value");
    const button = root.querySelector("#xz-mic-meter-button");
    let audioContext = null;
    let analyser = null;
    let data = null;
    let rafId = null;
    let starting = false;

    const paint = (level, statusText) => {
      const safeLevel = Math.max(0, Math.min(100, Math.round(level || 0)));
      window.xzMicMeter = window.xzMicMeter || {};
      window.xzMicMeter.level = safeLevel;
      window.xzMicMeter.updatedAt = Date.now();
      root.dataset.level = String(safeLevel);
      if (fill) fill.style.width = `${safeLevel}%`;
      if (value) value.textContent = `${safeLevel}%`;
      if (status && statusText && !(window.xzCallVad && window.xzCallVad.active)) status.textContent = statusText;
    };

    const loop = () => {
      if (!analyser || !data) return;
      analyser.getByteTimeDomainData(data);
      let sum = 0;
      let peak = 0;
      for (let index = 0; index < data.length; index += 1) {
        const sample = (data[index] - 128) / 128;
        sum += sample * sample;
        peak = Math.max(peak, Math.abs(sample));
      }
      const rms = Math.sqrt(sum / data.length);
      const level = Math.min(100, Math.max(rms * 320, peak * 120));
      const label = level < 2 ? "无输入" : level < 14 ? "较轻" : level < 58 ? "监听中" : "偏大";
      paint(level, label);
      rafId = requestAnimationFrame(loop);
    };

    const start = async () => {
      if (starting || analyser) return;
      if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        paint(0, "不可用");
        return;
      }
      starting = true;
      paint(0, "授权中");
      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          audio: {
            echoCancellation: true,
            noiseSuppression: true,
            autoGainControl: true,
          },
          video: false,
        });
        audioContext = new (window.AudioContext || window.webkitAudioContext)();
        const source = audioContext.createMediaStreamSource(stream);
        analyser = audioContext.createAnalyser();
        analyser.fftSize = 1024;
        analyser.smoothingTimeConstant = 0.72;
        data = new Uint8Array(analyser.fftSize);
        source.connect(analyser);
        window.xzMicMeter = window.xzMicMeter || {};
        window.xzMicMeter.stream = stream;
        window.xzMicMeter.audioContext = audioContext;
        window.xzMicMeter.analyser = analyser;
        window.xzMicMeter.source = source;
        if (button) button.textContent = "监听中";
        loop();
      } catch (err) {
        const name = err && err.name ? err.name : "";
        paint(0, name === "NotAllowedError" || name === "PermissionDeniedError" ? "未授权" : "不可用");
      } finally {
        starting = false;
      }
    };

    if (button) button.addEventListener("click", start);
    setTimeout(start, 600);
    window.addEventListener("beforeunload", () => {
      if (rafId) cancelAnimationFrame(rafId);
      if (audioContext) audioContext.close().catch(() => {});
    });
  };

  initMicMeter();
  setTimeout(initMicMeter, 1200);

  const initRoleDrawer = () => {
    const toggle = document.getElementById("xz-role-drawer-toggle");
    const toolbar = document.querySelector(".role-toolbar");
    if (!toggle || !toolbar || toggle.dataset.ready === "1") return;
    toggle.dataset.ready = "1";
    const setOpen = (open) => {
      toolbar.classList.toggle("role-toolbar-open", open);
      toggle.setAttribute("aria-expanded", open ? "true" : "false");
    };
    setOpen(false);
    toggle.addEventListener("click", () => {
      setOpen(!toolbar.classList.contains("role-toolbar-open"));
    });
  };

  initRoleDrawer();
  setTimeout(initRoleDrawer, 1200);

  const initCallWatchdog = () => {
    if (window.xzCallWatchdogReady) return;
    window.xzCallWatchdogReady = true;
    const isCallActiveInDom = () => {
      const panel = document.querySelector(".call-card-active");
      const buttonText = Array.from(document.querySelectorAll("button"))
        .map((button) => `${button.innerText || ""} ${button.textContent || ""}`.trim())
        .join(" ");
      return Boolean(panel) || /挂断/.test(buttonText);
    };
    setInterval(() => {
      if (!window.xzSyncCallRecording) return;
      const active = isCallActiveInDom();
      const vad = window.xzCallVad || {};
      if (active && !vad.active) {
        window.xzSyncCallRecording({ active: true, source: "dom-watchdog" });
      } else if (!active && vad.active) {
        window.xzSyncCallRecording({ active: false, source: "dom-watchdog" });
      }
    }, 500);
  };

  initCallWatchdog();
  setTimeout(initCallWatchdog, 1600);
}
"""

SPEAK_LAST_ASSISTANT_JS = """
(messages, character, speakEnabled) => {
  if (!speakEnabled || !window.xzSpeakLastAssistant) return [];
  setTimeout(() => window.xzSpeakLastAssistant(messages, character), 250);
  return [];
}
"""

PLAY_REPLY_AUDIO_JS = """
(speakEnabled, callState) => {
  const callActive = Boolean((callState && callState.active) || (window.xzCallVad && window.xzCallVad.active));
  const setCallStatus = (text) => {
    const status = document.getElementById("xz-mic-meter-status");
    if (status) status.textContent = text;
    const replyStatus = document.getElementById("xz-reply-guard-status");
    if (replyStatus) replyStatus.textContent = text;
  };
  const latestAudio = () => {
    const audios = Array.from(document.querySelectorAll("audio"))
      .filter((audio) => audio.currentSrc || audio.src);
    return audios[audios.length - 1] || null;
  };

  const clearCallCapture = () => {
    if (!window.xzCallVad) return;
    window.xzCallVad.clientHaveVoice = false;
    window.xzCallVad.clientVoiceStop = false;
    window.xzCallVad.clientVoiceWindow = [];
    window.xzCallVad.lastIsVoice = false;
    window.xzCallVad.lastVoiceAt = 0;
    window.xzCallVad.preRollFrames = [];
    window.xzCallVad.asrFrames = [];
    window.xzCallVad.frameRemainder = new Float32Array(0);
    window.xzCallVad.utteranceStartedAt = 0;
    window.xzCallVad.levelVoiceFrames = 0;
  };

  window.xzExitReplyGuard = (delay = 900) => {
    if (!window.xzCallVad) return;
    if (window.xzReplyGuardTimer) clearTimeout(window.xzReplyGuardTimer);
    clearCallCapture();
    window.xzCallVad.playingAssistantAudio = false;
    window.xzCallVad.awaitingAssistantAudio = false;
    window.xzCallVad.replyPlayingSrc = "";
    window.xzCallVad.processing = false;
    window.xzCallVad.replyGuardActive = false;
    window.xzCallVad.cooldownUntil = Date.now() + delay;
    setTimeout(() => {
      if (window.xzCallVad && window.xzCallVad.active && !window.xzCallVad.clientHaveVoice) {
        setCallStatus("自动监听");
      }
    }, delay + 80);
  };

  window.xzEnterReplyGuard = (label = "回复占用中", options = {}) => {
    if (!window.xzCallVad) window.xzCallVad = {};
    const active = Boolean(window.xzCallVad.active || callActive);
    clearCallCapture();
    window.xzCallVad.processing = active;
    window.xzCallVad.replyGuardActive = true;
    window.xzCallVad.playingAssistantAudio = Boolean(options.playing);
    window.xzCallVad.awaitingAssistantAudio = !options.playing;
    window.xzCallVad.processingStartedAt = Date.now();
    window.xzCallVad.cooldownUntil = Date.now() + (options.timeoutMs || 20000);
    if (window.xzReplyGuardTimer) clearTimeout(window.xzReplyGuardTimer);
    window.xzReplyGuardTimer = setTimeout(() => {
      if (window.xzCallVad && window.xzCallVad.replyGuardActive) window.xzExitReplyGuard(900);
    }, options.timeoutMs || 20000);
    setCallStatus(label);
  };

  window.xzSkipAssistantAudio = () => {
    if ("speechSynthesis" in window) window.speechSynthesis.cancel();
    document.querySelectorAll("audio").forEach((audio) => {
      try {
        audio.pause();
        audio.currentTime = 0;
      } catch {}
    });
    window.xzExitReplyGuard(500);
  };

  const audio = latestAudio();
  const src = audio ? (audio.currentSrc || audio.src || "") : "";
  const isNewAudio = Boolean(src && src !== window.xzLastReplyAudioSrc);
  const shouldPlay = speakEnabled !== false || callActive || isNewAudio;
  const playToken = `${Date.now()}-${Math.random()}`;

  if (callActive && window.xzCallVad) {
    window.xzEnterReplyGuard("回复展示中", { timeoutMs: 18000 });
    window.xzCallVad.replyPlayToken = playToken;
    setTimeout(() => {
      const vad = window.xzCallVad;
      if (vad && vad.active && vad.replyPlayToken === playToken && vad.awaitingAssistantAudio && !vad.playingAssistantAudio) {
        window.xzExitReplyGuard(700);
      }
    }, 3600);
  }

  if (!shouldPlay) {
    window.xzExitReplyGuard(700);
    return [];
  }

  const playLatestAudio = () => {
    const audio = latestAudio();
    if (!audio) return;
    try {
      const currentSrc = audio.currentSrc || audio.src || "";
      if (callActive && window.xzCallVad && window.xzCallVad.playingAssistantAudio) return;
      if (currentSrc) window.xzLastReplyAudioSrc = currentSrc;
      audio.currentTime = 0;
      if (callActive && window.xzCallVad) {
        window.xzEnterReplyGuard("语音播放中", { playing: true, timeoutMs: 24000 });
        window.xzCallVad.replyPlayingSrc = currentSrc;
        const durationMs = Number.isFinite(audio.duration) && audio.duration > 0 ? audio.duration * 1000 : 6000;
        window.xzCallVad.cooldownUntil = Date.now() + durationMs + 1400;
        let released = false;
        const release = () => {
          if (released) return;
          released = true;
          if (window.xzCallVad) {
            window.xzCallVad.awaitingAssistantAudio = false;
            window.xzCallVad.replyPlayingSrc = "";
          }
          window.xzExitReplyGuard(1200);
        };
        audio.addEventListener("ended", release, { once: true });
        audio.addEventListener("pause", () => {
          if (audio.currentTime > 0 && audio.currentTime >= Math.max(0, (audio.duration || 0) - 0.2)) release();
        }, { once: true });
        setTimeout(() => {
          if (window.xzCallVad && window.xzCallVad.playingAssistantAudio && window.xzLastReplyAudioSrc === currentSrc) {
            release();
          }
        }, durationMs + 1800);
      }
      const playPromise = audio.play();
      if (playPromise && playPromise.catch) playPromise.catch(() => window.xzExitReplyGuard(900));
    } catch {}
  };
  setTimeout(playLatestAudio, 350);
  setTimeout(playLatestAudio, 900);
  setTimeout(() => {
    if (window.xzCallVad && window.xzCallVad.active && !window.xzCallVad.playingAssistantAudio && !window.xzCallVad.awaitingAssistantAudio) {
      window.xzExitReplyGuard(800);
    }
  }, 3200);
  return [];
}
"""

PREVIEW_VOICE_JS = """
(character) => {
  const samples = {
    "胡桃小朋友": "嘿嘿，我是胡桃！前端拟声上线啦，快来和我聊天吧！",
    "名取同学": "你好，我是名取。接下来我会用低沉、成熟一点的声音，帮你把问题讲清楚。",
    "小乐（默认助手）": "你好，我是小乐。现在是本机语音预览。"
  };
  if (window.xzSpeakText) {
    window.xzSpeakText(samples[character] || samples["小乐（默认助手）"], character);
  }
  return [];
}
"""

STOP_SPEECH_JS = """
() => {
  if (window.xzSkipAssistantAudio) {
    window.xzSkipAssistantAudio();
  } else {
    if ("speechSynthesis" in window) window.speechSynthesis.cancel();
    document.querySelectorAll("audio").forEach((audio) => {
      try {
        audio.pause();
        audio.currentTime = 0;
      } catch {}
    });
    if (window.xzCallVad) {
      window.xzCallVad.processing = false;
      window.xzCallVad.playingAssistantAudio = false;
      window.xzCallVad.awaitingAssistantAudio = false;
      window.xzCallVad.replyGuardActive = false;
      window.xzCallVad.cooldownUntil = Date.now() + 500;
    }
  }
  const status = document.getElementById("xz-mic-meter-status");
  if (status) status.textContent = "自动监听";
  const replyStatus = document.getElementById("xz-reply-guard-status");
  if (replyStatus) replyStatus.textContent = "已跳过";
  return [];
}
"""

SYNC_CALL_RECORDING_JS = """
(callState) => {
  window.xzSyncCallRecording = window.xzSyncCallRecording || ((state) => {
    const active = Boolean(state && state.active);
    window.xzCallVad = window.xzCallVad || {};
    window.xzCallVad.active = active;
    return [];
  });
  if (window.xzSyncCallRecordingReady) return window.xzSyncCallRecording(callState);
  window.xzSyncCallRecordingReady = true;
  window.xzSyncCallRecording = (callState) => {
  const active = Boolean(callState && callState.active);
  window.xzCallVad = window.xzCallVad || {};
  window.xzCallVad.active = active;

  if ("speechSynthesis" in window) window.speechSynthesis.cancel();
  document.querySelectorAll("audio").forEach((audio) => {
    try {
      audio.pause();
      audio.currentTime = 0;
    } catch {}
  });

  const setCallStatus = (text) => {
    const status = document.getElementById("xz-mic-meter-status");
    if (status) status.textContent = text;
  };

  const readLevel = () => {
    if (window.xzMicMeter && Number.isFinite(window.xzMicMeter.level)) return window.xzMicMeter.level;
    const root = document.getElementById("xz-mic-meter");
    if (root && root.dataset.level) {
      const rootLevel = Number.parseFloat(root.dataset.level);
      if (Number.isFinite(rootLevel)) return rootLevel;
    }
    const value = document.getElementById("xz-mic-meter-value");
    if (!value) return 0;
    const parsed = Number.parseFloat(String(value.textContent || "0").replace("%", ""));
    return Number.isFinite(parsed) ? parsed : 0;
  };

  const findBridgeInput = () => {
    const root = document.getElementById("xz-call-audio-payload");
    if (!root) return null;
    if (root.matches && root.matches("textarea, input")) return root;
    return root.querySelector("textarea, input");
  };

  const findBridgeSubmit = () => {
    const root = document.getElementById("xz-call-audio-submit");
    if (!root) return null;
    if (root.matches && root.matches("button")) return root;
    return root.querySelector("button");
  };

  const setNativeValue = (element, value) => {
    if (!element) return false;
    const descriptor = Object.getOwnPropertyDescriptor(Object.getPrototypeOf(element), "value");
    if (descriptor && descriptor.set) {
      descriptor.set.call(element, value);
    } else {
      element.value = value;
    }
    element.dispatchEvent(new Event("input", { bubbles: true }));
    element.dispatchEvent(new Event("change", { bubbles: true }));
    return true;
  };

  const toBase64 = (bytes) => {
    let binary = "";
    const chunkSize = 0x8000;
    for (let offset = 0; offset < bytes.length; offset += chunkSize) {
      binary += String.fromCharCode.apply(null, bytes.subarray(offset, offset + chunkSize));
    }
    return btoa(binary);
  };

  const encodeWav = (samples, sampleRate) => {
    const channels = 1;
    const bytesPerSample = 2;
    const blockAlign = channels * bytesPerSample;
    const dataSize = samples.length * bytesPerSample;
    const buffer = new ArrayBuffer(44 + dataSize);
    const view = new DataView(buffer);
    const writeString = (offset, text) => {
      for (let index = 0; index < text.length; index += 1) view.setUint8(offset + index, text.charCodeAt(index));
    };
    writeString(0, "RIFF");
    view.setUint32(4, 36 + dataSize, true);
    writeString(8, "WAVE");
    writeString(12, "fmt ");
    view.setUint32(16, 16, true);
    view.setUint16(20, 1, true);
    view.setUint16(22, channels, true);
    view.setUint32(24, sampleRate, true);
    view.setUint32(28, sampleRate * blockAlign, true);
    view.setUint16(32, blockAlign, true);
    view.setUint16(34, 16, true);
    writeString(36, "data");
    view.setUint32(40, dataSize, true);
    let offset = 44;
    for (let index = 0; index < samples.length; index += 1, offset += 2) {
      const sample = Math.max(-1, Math.min(1, samples[index]));
      view.setInt16(offset, sample < 0 ? sample * 0x8000 : sample * 0x7fff, true);
    }
    return new Uint8Array(buffer);
  };

  const mergeChunks = (chunks) => {
    const total = chunks.reduce((sum, chunk) => sum + chunk.length, 0);
    const merged = new Float32Array(total);
    let offset = 0;
    chunks.forEach((chunk) => {
      merged.set(chunk, offset);
      offset += chunk.length;
    });
    return merged;
  };

  const resampleLinear = (samples, fromRate, toRate) => {
    if (!samples.length || fromRate === toRate) return samples;
    const ratio = fromRate / toRate;
    const length = Math.max(1, Math.round(samples.length / ratio));
    const output = new Float32Array(length);
    for (let index = 0; index < length; index += 1) {
      const sourceIndex = index * ratio;
      const left = Math.floor(sourceIndex);
      const right = Math.min(samples.length - 1, left + 1);
      const weight = sourceIndex - left;
      output[index] = samples[left] * (1 - weight) + samples[right] * weight;
    }
    return output;
  };

  const resetXiaozhiAudioState = () => {
    const vad = window.xzCallVad;
    vad.clientHaveVoice = false;
    vad.clientVoiceStop = false;
    vad.clientVoiceWindow = [];
    vad.lastIsVoice = false;
    vad.lastVoiceAt = 0;
    vad.preRollFrames = [];
    vad.asrFrames = [];
    vad.frameRemainder = new Float32Array(0);
    vad.utteranceStartedAt = 0;
  };

  const ensureRecorder = async () => {
    const vad = window.xzCallVad;
    if (vad.recorderReady) return true;
    const stream = window.xzMicMeter && window.xzMicMeter.stream
      ? window.xzMicMeter.stream
      : await navigator.mediaDevices.getUserMedia({
          audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
          video: false,
        });
    window.xzMicMeter = window.xzMicMeter || {};
    window.xzMicMeter.stream = stream;
    const AudioCtx = window.AudioContext || window.webkitAudioContext;
    const context = (window.xzMicMeter && window.xzMicMeter.audioContext) || new AudioCtx();
    window.xzMicMeter.audioContext = context;
    if (context.state === "suspended") await context.resume();
    const source = window.xzMicMeter.source || context.createMediaStreamSource(stream);
    window.xzMicMeter.source = source;
    const processor = context.createScriptProcessor(4096, 1, 1);
    processor.onaudioprocess = (event) => {
      if (!window.xzCallVad || !window.xzCallVad.active || window.xzCallVad.processing || window.xzCallVad.playingAssistantAudio || window.xzCallVad.awaitingAssistantAudio || window.xzCallVad.replyGuardActive) return;
      const input = event.inputBuffer.getChannelData(0);
      processAudioInput(new Float32Array(input));
    };
    source.connect(processor);
    processor.connect(context.destination);
    vad.audioContext = context;
    vad.processor = processor;
    vad.source = source;
    vad.sampleRate = context.sampleRate || 48000;
    vad.recorderReady = true;
    return true;
  };

  const submitAsrFrames = () => {
    const vad = window.xzCallVad;
    const frames = vad.asrFrames || [];
    vad.asrFrames = [];
    vad.preRollFrames = [];
    if (frames.length <= 15) return false;
    const samples = mergeChunks(frames);
    const durationMs = Math.round((samples.length / 16000) * 1000);
    if (durationMs < 300) return false;
    const wavBytes = encodeWav(samples, 16000);
    const payload = JSON.stringify({
      filename: `call-${Date.now()}.wav`,
      content_type: "audio/wav",
      audio_base64: toBase64(wavBytes),
      duration_ms: durationMs,
    });
    const input = findBridgeInput();
    const submit = findBridgeSubmit();
    if (!input || !submit) {
      setCallStatus("提交通道未就绪");
      return false;
    }
    setNativeValue(input, payload);
    submit.click();
    return true;
  };

  const startAudioStream = async () => {
    const vad = window.xzCallVad;
    if (vad.recorderReady || vad.starting) return true;
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      setCallStatus("麦克风不可用");
      return false;
    }
    vad.starting = true;
    try {
      await ensureRecorder();
      return true;
    } catch (err) {
      setCallStatus("麦克风未授权");
      return false;
    } finally {
      vad.starting = false;
    }
  };

  const handleVoiceFrame = (frame) => {
    const vad = window.xzCallVad;
    let sum = 0;
    let peak = 0;
    for (let index = 0; index < frame.length; index += 1) {
      const sample = frame[index];
      sum += sample * sample;
      peak = Math.max(peak, Math.abs(sample));
    }
    const rms = Math.sqrt(sum / frame.length);
    const frameLevel = Math.min(100, Math.max(rms * 320, peak * 120));
    const floor = updateNoiseFloor(frameLevel, false);
    const highThreshold = Math.max(4.2, floor + Math.max(2.2, floor * 0.32));
    const lowThreshold = Math.max(2.8, floor + Math.max(1.1, floor * 0.16));

    let isVoice = vad.lastIsVoice;
    if (frameLevel >= highThreshold) {
      isVoice = true;
    } else if (frameLevel <= lowThreshold) {
      isVoice = false;
    }
    vad.lastIsVoice = isVoice;

    vad.clientVoiceWindow = Array.isArray(vad.clientVoiceWindow) ? vad.clientVoiceWindow : [];
    vad.clientVoiceWindow.push(isVoice);
    if (vad.clientVoiceWindow.length > 5) vad.clientVoiceWindow.shift();
    const clientHaveVoice = vad.clientVoiceWindow.filter(Boolean).length >= 3;

    vad.preRollFrames = Array.isArray(vad.preRollFrames) ? vad.preRollFrames : [];
    vad.asrFrames = Array.isArray(vad.asrFrames) ? vad.asrFrames : [];

    if (!clientHaveVoice && !vad.clientHaveVoice) {
      vad.preRollFrames.push(frame);
      if (vad.preRollFrames.length > 10) vad.preRollFrames.shift();
      vad.debugFrameLevel = frameLevel;
      vad.debugThreshold = highThreshold;
      setCallStatus("自动监听");
      return;
    }

    if (clientHaveVoice && !vad.clientHaveVoice) {
      vad.clientHaveVoice = true;
      vad.utteranceStartedAt = Date.now();
      vad.lastVoiceAt = Date.now();
      vad.asrFrames = vad.preRollFrames.concat([frame]);
      vad.preRollFrames = [];
      vad.debugFrameLevel = frameLevel;
      vad.debugThreshold = highThreshold;
      setCallStatus("正在收音");
      return;
    }

    if (vad.clientHaveVoice) {
      vad.asrFrames.push(frame);
      if (clientHaveVoice) {
        vad.lastVoiceAt = Date.now();
        setCallStatus("正在收音");
      } else {
        const stopDuration = Date.now() - (vad.lastVoiceAt || Date.now());
        const elapsed = Date.now() - (vad.utteranceStartedAt || Date.now());
        if (stopDuration >= 200 || elapsed >= 30000) {
          vad.clientVoiceStop = true;
        }
      }
    }

    if (vad.clientVoiceStop) {
      const submitted = submitAsrFrames();
      resetXiaozhiAudioState();
      vad.processing = submitted;
      vad.submitting = submitted;
      vad.processingStartedAt = Date.now();
      vad.cooldownUntil = Date.now() + 900;
      setCallStatus(submitted ? "处理中" : "自动监听");
    }
  };

  const processAudioInput = (input) => {
    const vad = window.xzCallVad;
    if (!vad || !vad.active || vad.processing || vad.playingAssistantAudio || vad.awaitingAssistantAudio || vad.replyGuardActive) return;
    const sourceRate = vad.sampleRate || 48000;
    const samples16k = resampleLinear(input, sourceRate, 16000);
    const previous = vad.frameRemainder || new Float32Array(0);
    const combined = new Float32Array(previous.length + samples16k.length);
    combined.set(previous, 0);
    combined.set(samples16k, previous.length);
    const frameSize = 960; // 60ms at 16kHz, matching Xiaozhi audio_params.frame_duration.
    let offset = 0;
    while (offset + frameSize <= combined.length) {
      handleVoiceFrame(combined.slice(offset, offset + frameSize));
      offset += frameSize;
    }
    vad.frameRemainder = combined.slice(offset);
  };

  const updateNoiseFloor = (level, force = false) => {
    const vad = window.xzCallVad;
    if (!Number.isFinite(vad.noiseFloor)) vad.noiseFloor = Math.max(1, Math.min(18, level || 1));
    if (force) {
      vad.noiseFloor = vad.noiseFloor * 0.82 + level * 0.18;
      return vad.noiseFloor;
    }
    const nearFloor = level <= vad.noiseFloor + Math.max(2, vad.noiseFloor * 0.22);
    if (nearFloor) {
      vad.noiseFloor = vad.noiseFloor * 0.92 + level * 0.08;
    } else {
      vad.noiseFloor = vad.noiseFloor * 0.998 + Math.min(level, vad.noiseFloor + 1) * 0.002;
    }
    vad.noiseFloor = Math.max(0.5, Math.min(55, vad.noiseFloor));
    return vad.noiseFloor;
  };

  const rememberLevel = (level) => {
    const vad = window.xzCallVad;
    vad.levels = Array.isArray(vad.levels) ? vad.levels : [];
    vad.levels.push(level);
    if (vad.levels.length > 16) vad.levels.shift();
  };

  const stopLoop = () => {
    if (window.xzCallVad.timer) clearInterval(window.xzCallVad.timer);
    window.xzCallVad.timer = null;
    window.xzCallVad.levels = [];
    window.xzCallVad.processing = false;
    window.xzCallVad.submitting = false;
    window.xzCallVad.starting = false;
    window.xzCallVad.cooldownUntil = 0;
    window.xzCallVad.playingAssistantAudio = false;
    window.xzCallVad.awaitingAssistantAudio = false;
    window.xzCallVad.replyPlayingSrc = "";
    window.xzCallVad.replyGuardActive = false;
    resetXiaozhiAudioState();
    setCallStatus("待机");
  };

  if (!active) {
    stopLoop();
    return [];
  }

  if (window.xzCallVad.timer) clearInterval(window.xzCallVad.timer);
  window.xzCallVad.levels = [];
  window.xzCallVad.processing = false;
  window.xzCallVad.submitting = false;
  window.xzCallVad.starting = false;
  window.xzCallVad.cooldownUntil = 0;
  window.xzCallVad.playingAssistantAudio = false;
  window.xzCallVad.awaitingAssistantAudio = false;
  window.xzCallVad.replyPlayingSrc = "";
  window.xzCallVad.replyGuardActive = false;
  window.xzCallVad.calibratingUntil = Date.now() + 850;
  updateNoiseFloor(readLevel(), true);
  resetXiaozhiAudioState();
  startAudioStream();
  setCallStatus("校准底噪");

  window.xzCallVad.timer = setInterval(() => {
    if (!window.xzCallVad.active) {
      stopLoop();
      return;
    }

    const now = Date.now();
    if (window.xzCallVad.processing || window.xzCallVad.playingAssistantAudio || window.xzCallVad.awaitingAssistantAudio || window.xzCallVad.replyGuardActive) {
      if (now - (window.xzCallVad.processingStartedAt || now) > 185000) {
        window.xzCallVad.processing = false;
        window.xzCallVad.playingAssistantAudio = false;
        window.xzCallVad.awaitingAssistantAudio = false;
        window.xzCallVad.replyGuardActive = false;
        window.xzCallVad.cooldownUntil = Date.now() + 900;
      } else {
        setCallStatus(window.xzCallVad.playingAssistantAudio ? "语音播放中" : window.xzCallVad.replyGuardActive ? "回复占用中" : "等待回复");
        return;
      }
    }

    if (now < (window.xzCallVad.cooldownUntil || 0)) {
      setCallStatus("等待回复");
      return;
    }

    const level = readLevel();
    rememberLevel(level);
    const floor = updateNoiseFloor(level, !window.xzCallVad.clientHaveVoice && now < (window.xzCallVad.calibratingUntil || 0));

    if (now < (window.xzCallVad.calibratingUntil || 0)) {
      setCallStatus("校准底噪");
      return;
    }

    if (!window.xzCallVad.recorderReady && !window.xzCallVad.starting) {
      startAudioStream();
      setCallStatus("麦克风启动中");
      return;
    }

    if (window.xzCallVad.clientHaveVoice) {
      const count = (window.xzCallVad.asrFrames || []).length;
      setCallStatus(`正在收音 ${count}帧`);
    } else {
      const voiceHint = level >= Math.max(4.5, floor + Math.max(2.5, floor * 0.35));
      window.xzCallVad.levelVoiceFrames = voiceHint ? (window.xzCallVad.levelVoiceFrames || 0) + 1 : 0;
      if (window.xzCallVad.levelVoiceFrames >= 3 && (window.xzCallVad.preRollFrames || []).length > 0) {
        window.xzCallVad.clientHaveVoice = true;
        window.xzCallVad.utteranceStartedAt = Date.now();
        window.xzCallVad.lastVoiceAt = Date.now();
        window.xzCallVad.asrFrames = (window.xzCallVad.preRollFrames || []).slice();
        window.xzCallVad.preRollFrames = [];
        setCallStatus(`正在收音 ${window.xzCallVad.asrFrames.length}帧`);
      } else {
        setCallStatus(`自动监听 ${Math.round(level)}%`);
      }
    }
  }, 120);

  return [];
  };
  return window.xzSyncCallRecording(callState);
}
"""

APP_BOOT_JS = """
() => {
  try {
    (""" + SYNC_CALL_RECORDING_JS + """)({ active: false, source: "app-boot" });
  } catch (err) {
    console.error("xiaozhi call boot failed", err);
  }
  try {
    return (""" + VOICE_PREVIEW_JS + """)();
  } catch (err) {
    console.error("xiaozhi frontend boot failed", err);
    return [];
  }
}
"""



WELCOME_MESSAGES: list[dict[str, str]] = [
    {
        "role": "assistant",
        "content": "你好，我是智能语音聊天助手。你可以录音、上传音频，或者直接输入文字来测试前端交互。",
    }
]

VOICE_CORE_ENDPOINT = os.getenv("VOICE_CORE_ENDPOINT", "http://127.0.0.1:8010/ask")
VOICE_CORE_TTS_ENDPOINT = os.getenv("VOICE_CORE_TTS_ENDPOINT", "http://127.0.0.1:8010/tts")
VOICE_CORE_AUDIO_DIR = VOICE_CORE_DIR / "tmp" / "fastapi_audio"
USER_AVATAR_DIR = WEB_STATIC_DIR / "user_avatars"
DEFAULT_USER_AVATAR = "/static/avatars/user.svg"
DEFAULT_USER_AVATAR_PATH = WEB_STATIC_DIR / "avatars" / "user.svg"


def resolve_voice_core_audio_path(audio_url: str | None) -> str | None:
    if not audio_url:
        return None
    filename = Path(audio_url).name
    if not filename:
        return None
    audio_path = VOICE_CORE_AUDIO_DIR / filename
    return str(audio_path) if audio_path.exists() else None

# ── 角色档案（数字人角色配置） ─────
CHARACTER_PROFILES: dict[str, dict[str, Any]] = {
    "小乐（默认助手）": {
        "name": "小乐",
        "tag": "通用助手",
        "avatar_color": "#0f8f72",
        "avatar_letter": "乐",
        "avatar_image": "/static/avatars/xiaole-preview.png",
        "personality": "友善、专业的通用智能助手，擅长自然对话和任务处理。",
        "speech_hint": "萝莉向：高一点、轻一点、快一点",
        "edge_voice": "zh-CN-XiaoyiNeural",
        "edge_rate": "+18%",
        "edge_pitch": "+24Hz",
        "edge_volume": "+0%",
        "system_prompt": (
            "你是小乐，一个友善且专业的智能语音助手。"
            "请用自然、亲切、轻快一点的口吻与用户交流。"
        ),
        "default_voice": "小乐萝莉音",
        "greeting": (
            "你好，我是小乐！你的智能语音助手。"
            "你可以录音、上传音频，或者直接输入文字来和我聊天。"
        ),
    },
    "春日姐姐": {
        "name": "春日",
        "tag": "温柔知心",
        "avatar_color": "#e8837c",
        "avatar_letter": "春",
        "avatar_image": "/static/avatars/haruhi.svg",
        "personality": "温柔体贴的大姐姐，说话柔和，善于倾听，给人安心的感觉。",
        "speech_hint": "柔和姐姐音",
        "edge_voice": "zh-CN-XiaoxiaoNeural",
        "edge_rate": "-4%",
        "edge_pitch": "-2Hz",
        "edge_volume": "+0%",
        "system_prompt": (
            "你是春日，一个温柔知心的大姐姐角色。"
            "说话柔和、体贴，善于倾听和安慰他人。请用温暖的语气回复。"
        ),
        "default_voice": "春日柔和姐姐音",
        "greeting": (
            "你好呀，我是春日。有什么想和我聊的吗？"
            "不管是开心的还是烦恼的，都可以告诉我哦。"
        ),
    },
    "名取同学": {
        "name": "名取",
        "tag": "成熟港风男中音",
        "avatar_color": "#7c6fbd",
        "avatar_letter": "名",
        "avatar_image": "/static/avatars/natori-preview.png",
        "personality": "冷静、成熟、沉稳的男同学，表达有条理，擅长分析和解答复杂问题。",
        "speech_hint": "成熟港风男中音：低沉、厚一点、语速正常",
        "edge_voice": "zh-HK-WanLungNeural",
        "edge_rate": "-4%",
        "edge_pitch": "-46Hz",
        "edge_volume": "+4%",
        "system_prompt": (
            "你是名取，一个冷静、成熟、沉稳的男同学角色。"
            "表达清晰、有条理，擅长分析和解答问题。请用低调、稳重、厚实而专业的语气回复。"
        ),
        "default_voice": "名取成熟港风男中音",
        "greeting": (
            "你好，我是名取。有什么问题需要我帮忙分析吗？"
            "我会尽力给你一个清晰的解答。"
        ),
    },
    "胡桃小朋友": {
        "name": "胡桃",
        "tag": "活泼可爱",
        "avatar_color": "#e6a23c",
        "avatar_letter": "桃",
        "avatar_image": "/static/avatars/hutao-preview.png",
        "personality": "活泼、古灵精怪、节奏快一点，说话俏皮有趣，偶尔用颜文字。",
        "speech_hint": "萝莉音：高一点、轻一点、快一点",
        "edge_voice": "zh-TW-HsiaoYuNeural",
        "edge_rate": "+24%",
        "edge_pitch": "+36Hz",
        "edge_volume": "+0%",
        "system_prompt": (
            "你是胡桃，一个活泼可爱、充满元气的小朋友。"
            "说话古灵精怪，句子短一点，节奏轻快，偶尔用颜文字（如 (≧▽≦) 或 (｡•̀ᴗ-)✧），充满活力。"
        ),
        "default_voice": "胡桃萝莉音",
        "greeting": (
            "嘿嘿，你好呀！我是胡桃！快来和我聊天吧，超级开心的！(≧▽≦)"
        ),
    },
}

DEFAULT_CHARACTER = "小乐（默认助手）"
CHARACTER_NAMES = ["小乐（默认助手）", "名取同学", "胡桃小朋友"]


def get_character(name: str) -> dict[str, str]:
    return CHARACTER_PROFILES.get(name, CHARACTER_PROFILES[DEFAULT_CHARACTER])


def get_welcome_messages(char_name: str) -> list[dict[str, str]]:
    c = get_character(char_name)
    return [{"role": "assistant", "content": c["greeting"]}]


def get_character_voice(char_name: str) -> str:
    return get_character(char_name).get("default_voice", "清晰女声")


def get_character_edge_voice(char_name: str) -> str:
    return get_character(char_name).get("edge_voice", "zh-CN-XiaoyiNeural")


def get_character_voice_params(char_name: str) -> dict[str, str]:
    c = get_character(char_name)
    return {
        "voice": c.get("edge_voice", "zh-CN-XiaoyiNeural"),
        "voice_rate": c.get("edge_rate", "+0%"),
        "voice_pitch": c.get("edge_pitch", "+0Hz"),
        "voice_volume": c.get("edge_volume", "+0%"),
    }


def build_character_card(name: str) -> str:
    c = get_character(name)
    img_src = c.get("avatar_image", "")
    speech_hint = c.get("speech_hint", c["default_voice"])
    return (
        f'<div class="char-card">'
        f'  <img class="char-avatar-img" src="{img_src}" alt="{c["name"]}"/>'
        f'  <div class="char-info">'
        f'    <div class="char-name">{c["name"]}<span class="char-tag">{c["tag"]}</span></div>'
        f'    <div class="char-desc">{c["personality"]}</div>'
        f'    <div class="char-meta-row"><span class="voice-chip">绑定音色：{c["default_voice"]}</span><span class="voice-chip">{speech_hint}</span></div>'
        f"  </div>"
        f"</div>"
    )


# Live2D 角色名映射
LIVE2D_MODEL_MAP = {
    "小乐（默认助手）": "hiyori_pro_zh",
    "名取同学": "natori_pro_zh",
    "胡桃小朋友": "hutao_mmd",
}


def build_live2d_viewer(char_name: str = DEFAULT_CHARACTER) -> str:
    """返回一个 iframe，指向独立的 Live2D 页面（绕过 Gradio 的脚本限制）。"""
    model_name = LIVE2D_MODEL_MAP.get(char_name, "hiyori_pro_zh")
    return (
        f'<div class="live2d-section">'
        f'<iframe id="live2d-frame" src="/live2d-viewer?model={model_name}&v=7" '
        f'style="width:100%;height:620px;border:none;overflow:hidden;" '
        f'allow="autoplay"></iframe>'
        f'</div>'
    )


def describe_audio(audio_path: str | None) -> tuple[str, str]:
    if not audio_path:
        return "未上传音频", "0 KB"

    path = Path(audio_path)
    size_text = f"{path.stat().st_size / 1024:.1f} KB" if path.exists() else "未知大小"
    duration = "时长待识别"

    try:
        with wave.open(str(path), "rb") as audio_file:
            frames = audio_file.getnframes()
            rate = audio_file.getframerate()
            if rate:
                duration = f"{frames / float(rate):.1f} 秒"
    except Exception:
        duration = "已接收音频"

    return duration, size_text


def fake_transcript(text: str, audio_path: str | None) -> str:
    if text.strip():
        return text.strip()

    duration, _ = describe_audio(audio_path)
    if audio_path:
        return f"已收到一段语音输入，{duration}。这里显示模拟的 ASR 识别文本。"

    return ""


def build_reply(transcript: str, mode: str, voice_style: str, char_name: str = DEFAULT_CHARACTER) -> str:
    if not transcript:
        return "请先录制语音、上传音频，或输入一段文字。"

    c = get_character(char_name)
    char_name_cn = c['name']

    if char_name == "胡桃小朋友":
        return (
            f"嘿嘿，我听见啦：{transcript}\n\n"
            "这句先交给胡桃保管！现在还没有后端，我就先用前端小脑袋陪你聊。"
            "等真实接口接上，识别、回复、声音就能一条线串起来啦，出发出发！"
        )

    suggestions = {
        "日常聊天": f"我会以「{char_name_cn}」的身份，用自然口吻继续对话，并保留上下文。",
    }
    fallback_msg = f"我会以「{char_name_cn}」的身份按通用助手流程处理。"

    return (
        f"已识别到：{transcript}\n\n"
        f"当前模式是「{mode}」，{suggestions.get(mode, fallback_msg)}\n\n"
        f"当前绑定音色是「{voice_style}」。真实后端接入后，这里会替换成小乐服务返回的文本和语音。"
    )


def build_crm_data(transcript: str) -> dict[str, str]:
    name = "待识别"
    intent = "语音咨询"
    priority = "普通"
    next_action = "等待更多信息"

    if any(word in transcript for word in ["报名", "预约", "购买", "咨询"]):
        intent = "高意向咨询"
        priority = "优先跟进"
        next_action = "安排人工回访"
    if "张" in transcript:
        name = "张同学"
    if "小乐" in transcript:
        name = "小乐咨询用户"

    return {
        "user_name": name,
        "intent": intent,
        "priority": priority,
        "next_action": next_action,
        "last_input": transcript or "暂无",
    }


def extract_profile(transcript: str) -> str:
    crm = build_crm_data(transcript)

    return f"""
### CRM 信息预览

| 字段 | 识别结果 |
| --- | --- |
| 用户称呼 | {crm["user_name"]} |
| 用户意向 | {crm["intent"]} |
| 跟进优先级 | {crm["priority"]} |
| 下一步动作 | {crm["next_action"]} |
| 最近输入 | {crm["last_input"]} |
"""


def status_markdown(mode: str, audio_path: str | None) -> str:
    duration, size_text = describe_audio(audio_path)

    return f"""
<div class="status-pill">前端状态：可交互</div>

<div class="metric-grid" style="margin-top:12px;">
  <div class="metric"><b>{mode}</b><span>对话模式</span></div>
  <div class="metric"><b>{duration}</b><span>音频状态</span></div>
  <div class="metric"><b>{size_text}</b><span>文件大小</span></div>
</div>
"""


def build_assistant_insights(transcript: str, mode: str, voice_style: str, char_name: str = DEFAULT_CHARACTER) -> str:
    crm = build_crm_data(transcript)
    c = get_character(char_name)
    length_text = f"{len(transcript)} 字" if transcript else "等待输入"
    status_text = "已生成本轮分析" if transcript else "等待语音或文字"

    return f"""
<div class="status-pill">{status_text}</div>
<ul class="insight-list" style="margin-top:12px;">
  <li><strong>当前角色：</strong>{c['name']}（{c['tag']}）</li>
  <li><strong>识别长度：</strong>{length_text}</li>
  <li><strong>当前场景：</strong>{mode}</li>
  <li><strong>回复音色：</strong>{voice_style}</li>
  <li><strong>用户意向：</strong>{crm["intent"]}</li>
  <li><strong>跟进优先级：</strong>{crm["priority"]}</li>
</ul>
"""


def build_acceptance_panel(done: bool = False) -> str:
    chat_status = "已通过" if done else "待测试"
    crm_status = "已更新" if done else "待生成"
    reply_status = "已生成" if done else "待生成"

    return f"""
<div class="check-grid">
  <div class="check-item"><b>语音/文字输入</b><span>{chat_status}</span></div>
  <div class="check-item"><b>ASR 识别结果</b><span>{reply_status}</span></div>
  <div class="check-item"><b>助手回复</b><span>{reply_status}</span></div>
  <div class="check-item"><b>CRM 信息抽取</b><span>{crm_status}</span></div>
</div>
"""


def build_mock_api_response(payload: dict[str, Any]) -> dict[str, Any]:
    text = str(payload.get("text") or "")
    audio_path = payload.get("audio_path")
    mode = str(payload.get("mode") or "日常聊天")
    char_name = str(payload.get("char_name") or DEFAULT_CHARACTER)
    voice_style = get_character_voice(char_name)
    transcript = fake_transcript(text, audio_path)
    crm = build_crm_data(transcript)

    return {
        "success": True,
        "request_id": f"mock-{time.strftime('%Y%m%d-%H%M%S')}",
        "asr_text": transcript,
        "reply_text": build_reply(transcript, mode, voice_style, char_name),
        "tts_audio_url": "/mock/audio/xiaole-demo-reply.wav",
        "crm": crm,
        "tool_status": {
            "asr": "mock-whisper",
            "llm": "mock-xiaole-agent",
            "tts": "mock-tts",
            "crm": "mock-crm-writer",
        },
        "timings_ms": {
            "audio_receive": 36,
            "asr": 128,
            "dialogue": 342,
            "tts": 219,
        },
        "trace": [
            {"step": "receive_input", "message": "已接收 Gradio 前端请求"},
            {"step": "speech_to_text", "message": "已生成模拟 ASR 文本"},
            {"step": "dialogue", "message": "已生成模拟助手回复"},
            {"step": "crm_extract", "message": "已提取 CRM 预览字段"},
        ],
    }


def encode_multipart_form(
    fields: dict[str, Any],
    files: dict[str, tuple[str, bytes, str]],
) -> tuple[bytes, str]:
    boundary = f"----xiaozhi-gradio-{uuid.uuid4().hex}"
    chunks: list[bytes] = []

    for name, value in fields.items():
        if value is None:
            continue
        chunks.extend(
            [
                f"--{boundary}\r\n".encode("utf-8"),
                f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode("utf-8"),
                str(value).encode("utf-8"),
                b"\r\n",
            ]
        )

    for name, (filename, content, content_type) in files.items():
        chunks.extend(
            [
                f"--{boundary}\r\n".encode("utf-8"),
                (
                    f'Content-Disposition: form-data; name="{name}"; '
                    f'filename="{filename}"\r\n'
                ).encode("utf-8"),
                f"Content-Type: {content_type}\r\n\r\n".encode("utf-8"),
                content,
                b"\r\n",
            ]
        )

    chunks.append(f"--{boundary}--\r\n".encode("utf-8"))
    return b"".join(chunks), f"multipart/form-data; boundary={boundary}"


def normalize_backend_response(data: dict[str, Any], text: str) -> dict[str, Any]:
    answer_source = data.get("answer_source") or "llm"
    sources = []
    enterprise = data.get("enterprise") or {}
    for item in enterprise.get("sources") or []:
        sources.append(f"{item.get('title')}（{item.get('id')}）")
    return {
        "success": True,
        "request_id": data.get("session_id"),
        "asr_text": data.get("input_text") or text,
        "reply_text": data.get("answer_text") or "",
        "tts_audio_url": data.get("audio_url"),
        "tts_audio_path": resolve_voice_core_audio_path(data.get("audio_url")),
        "answer_source": answer_source,
        "sources": sources,
        "timings_ms": data.get("timings_ms") or {},
        "crm": build_crm_data(data.get("input_text") or text),
        "backend_errors": data.get("errors") or [],
    }


def call_backend(endpoint: str, payload: dict[str, Any]) -> tuple[dict[str, Any], str]:
    text = str(payload.get("text") or "").strip()
    audio_path = payload.get("audio_path")
    audio_base64 = payload.get("audio_base64")
    audio_filename = payload.get("audio_filename") or "audio.wav"
    audio_content_type = payload.get("audio_content_type") or "audio/wav"
    history = payload.get("history") or []
    return_audio = bool(payload.get("return_audio"))
    session_id = str(payload.get("session_id") or "gradio-live2d-session")
    body = {
        "text": text,
        "return_audio": return_audio,
        "include_audio_base64": False,
        "voice": payload.get("voice"),
        "voice_rate": payload.get("voice_rate"),
        "voice_pitch": payload.get("voice_pitch"),
        "voice_volume": payload.get("voice_volume"),
        "session_id": session_id,
        "history": history[-8:] if isinstance(history, list) else [],
        "audio_filename": audio_filename,
        "audio_content_type": audio_content_type,
    }

    try:
        if audio_base64:
            body["audio_base64"] = audio_base64
            req = request.Request(
                endpoint,
                data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
                headers={"Content-Type": "application/json; charset=utf-8"},
                method="POST",
            )
        elif audio_path:
            path = Path(audio_path)
            if not path.exists() or not path.is_file():
                raise FileNotFoundError(f"录音文件不存在：{audio_path}")
            filename = path.name
            content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
            multipart_body, content_type_header = encode_multipart_form(
                {
                    "text": text,
                    "return_audio": str(return_audio).lower(),
                    "include_audio_base64": "false",
                    "voice": payload.get("voice"),
                    "voice_rate": payload.get("voice_rate"),
                    "voice_pitch": payload.get("voice_pitch"),
                    "voice_volume": payload.get("voice_volume"),
                    "session_id": session_id,
                    "history": json.dumps(body["history"], ensure_ascii=False),
                },
                {
                    "audio": (
                        filename,
                        path.read_bytes(),
                        content_type,
                    )
                },
            )
            req = request.Request(
                endpoint,
                data=multipart_body,
                headers={"Content-Type": content_type_header},
                method="POST",
            )
        else:
            req = request.Request(
                endpoint,
                data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
                headers={"Content-Type": "application/json; charset=utf-8"},
                method="POST",
            )

        timeout_seconds = 180 if audio_path or audio_base64 else 60
        started_at = time.perf_counter()
        with request.urlopen(req, timeout=timeout_seconds) as response:
            data = json.loads(response.read().decode("utf-8"))
        normalized = normalize_backend_response(data, text)
        normalized["frontend_backend_elapsed_ms"] = int((time.perf_counter() - started_at) * 1000)
        return normalized, "voice_core"
    except error.HTTPError as exc:
        detail = exc.reason
        try:
            body_text = exc.read().decode("utf-8", errors="ignore")
            if body_text:
                detail = body_text
        except Exception:
            pass
        fallback = build_mock_api_response(payload)
        fallback["success"] = False
        fallback["error"] = f"真实后端返回错误，已使用本地兜底数据：{detail}"
        return fallback, "local_fallback"
    except (OSError, error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        fallback = build_mock_api_response(payload)
        fallback["success"] = False
        fallback["error"] = f"真实后端调用失败，已使用本地兜底数据：{exc}"
        return fallback, "local_fallback"


def preview_character_voice(char_name: str) -> str | None:
    char_name = char_name or DEFAULT_CHARACTER
    samples = {
        "胡桃小朋友": "嘿嘿，我是胡桃！这是更轻快一点的萝莉音，快来和我聊天吧！",
        "名取同学": "你好，我是名取。接下来我会用低沉、成熟一点的声音，帮你把问题讲清楚。",
        "小乐（默认助手）": "你好，我是小乐。现在是更轻快一点的萝莉向语音。",
    }
    body = {
        "text": samples.get(char_name, samples[DEFAULT_CHARACTER]),
        "session_id": "preview-voice",
        **get_character_voice_params(char_name),
    }
    req = request.Request(
        VOICE_CORE_TTS_ENDPOINT,
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=30) as response:
            data = json.loads(response.read().decode("utf-8"))
        return resolve_voice_core_audio_path(data.get("audio_url"))
    except (error.URLError, TimeoutError, json.JSONDecodeError):
        return None


def synthesize_reply_audio(text: str, char_name: str, session_id: str = "reply-voice") -> str | None:
    text = str(text or "").strip()
    if not text:
        return None
    text = compact_tts_text(text)
    body = {
        "text": text,
        "session_id": session_id,
        **get_character_voice_params(char_name or DEFAULT_CHARACTER),
    }
    req = request.Request(
        VOICE_CORE_TTS_ENDPOINT,
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=30) as response:
            data = json.loads(response.read().decode("utf-8"))
        return resolve_voice_core_audio_path(data.get("audio_url"))
    except (error.URLError, TimeoutError, json.JSONDecodeError):
        return None


def compact_tts_text(text: str, max_chars: int = 320) -> str:
    clean = str(text or "").strip()
    for marker in ["\n\n知识库来源：", "\n\n相关参考：", "\n\n【"]:
        if marker in clean:
            clean = clean.split(marker, 1)[0].strip()
    clean = clean.replace("**", "")
    if len(clean) <= max_chars:
        return clean
    return clean[:max_chars].rstrip("，。；、\n ") + "。"


def synthesize_last_assistant_audio(
    history: list[dict[str, Any]] | None,
    char_name: str,
    text_reply_voice_enabled: bool,
) -> str | None:
    if not text_reply_voice_enabled:
        return None
    for item in reversed(list(history or [])):
        if isinstance(item, dict) and item.get("role") == "assistant":
            text = str(item.get("content") or "")
            text = text.split("\n\n【", 1)[0].strip()
            return synthesize_reply_audio(text, char_name, "text-reply-voice")
    return None


def submit_message(
    audio_path: str | None,
    text: str,
    mode: str,
    char_name: str,
    text_reply_voice_enabled: bool,
    history: list[dict[str, Any]] | None,
    request_obj: gr.Request,
) -> tuple[list[dict[str, Any]], str, str, str, str, str, str, str, str | None]:
    char_name = char_name or DEFAULT_CHARACTER
    username = get_current_user_from_gradio(request_obj)
    voice_style = get_character_voice(char_name)
    voice_params = get_character_voice_params(char_name)
    history = list(history or load_user_history(username, char_name))
    payload = {
        "text": text,
        "audio_path": audio_path,
        "audio_summary": describe_audio(audio_path),
        "mode": mode,
        "voice_style": voice_style,
        "char_name": char_name,
        **voice_params,
        "return_audio": bool(text_reply_voice_enabled or audio_path),
        "history": history,
        "session_id": user_session_id(username),
        "client": "gradio-stage-1",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    api_data, _source = call_backend(VOICE_CORE_ENDPOINT, payload)
    transcript = str(api_data.get("asr_text") or "")

    if not transcript:
        return (
            history,
            "",
            status_markdown(mode, audio_path),
            build_assistant_insights("", mode, voice_style, char_name),
            extract_profile(""),
            build_acceptance_panel(False),
            text,
            build_character_card(char_name),
            None,
        )

    reply = str(api_data.get("reply_text") or build_reply(transcript, mode, voice_style, char_name))
    if api_data.get("answer_source") == "enterprise_knowledge_base":
        source_text = "、".join(api_data.get("sources") or [])
        if source_text:
            reply = f"{reply}\n\n【企业知识库来源】{source_text}"
    elif api_data.get("error"):
        reply = f"{reply}\n\n【提示】{api_data['error']}"
    history.append({"role": "user", "content": transcript})
    history.append({"role": "assistant", "content": reply})
    save_user_history(username, char_name, history)

    return (
        history,
        transcript,
        status_markdown(mode, audio_path),
        build_assistant_insights(transcript, mode, voice_style, char_name),
        extract_profile(transcript),
        build_acceptance_panel(True),
        "",
        build_character_card(char_name),
        api_data.get("tts_audio_path"),
    )


def submit_text_message(
    text: str,
    mode: str,
    char_name: str,
    _text_reply_voice_enabled: bool,
    history: list[dict[str, Any]] | None,
    request_obj: gr.Request,
) -> tuple[list[dict[str, Any]], str, str, str, str, str, str, str, str | None]:
    # Text submissions should render as soon as the LLM answer is ready; browser TTS handles optional speech.
    return submit_message(None, text, mode, char_name, False, history, request_obj)


def submit_call_audio(
    audio_payload: str,
    mode: str,
    char_name: str,
    history: list[dict[str, Any]] | None,
    request_obj: gr.Request,
) -> tuple[list[dict[str, Any]], str, str, str, str, str, str, str, str | None, str]:
    char_name = char_name or DEFAULT_CHARACTER
    username = get_current_user_from_gradio(request_obj)
    voice_style = get_character_voice(char_name)
    voice_params = get_character_voice_params(char_name)
    history = list(history or load_user_history(username, char_name))
    mode = mode or "日常聊天"
    try:
        payload_data = json.loads(audio_payload or "{}")
    except json.JSONDecodeError:
        payload_data = {}

    audio_base64 = str(payload_data.get("audio_base64") or "").strip()
    if not audio_base64:
        return (
            history,
            "",
            status_markdown(mode, None),
            build_assistant_insights("", mode, voice_style, char_name),
            extract_profile(""),
            build_acceptance_panel(False),
            "",
            build_character_card(char_name),
            None,
            "",
        )

    payload = {
        "text": "",
        "audio_base64": audio_base64,
        "audio_filename": payload_data.get("filename") or "call.wav",
        "audio_content_type": payload_data.get("content_type") or "audio/wav",
        "mode": mode,
        "voice_style": voice_style,
        "char_name": char_name,
        **voice_params,
        "return_audio": True,
        "history": history,
        "session_id": user_session_id(username),
        "client": "gradio-call-vad",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    api_data, _source = call_backend(VOICE_CORE_ENDPOINT, payload)
    transcript = str(api_data.get("asr_text") or "")

    if not transcript:
        history.append({
            "role": "assistant",
            "content": "我这边收到了一段声音，但没有识别出有效文字。你可以靠近麦克风再说一次。",
        })
        save_user_history(username, char_name, history)
        return (
            history,
            "",
            status_markdown(mode, None),
            build_assistant_insights("", mode, voice_style, char_name),
            extract_profile(""),
            build_acceptance_panel(False),
            "",
            build_character_card(char_name),
            None,
            "",
        )

    reply = str(api_data.get("reply_text") or build_reply(transcript, mode, voice_style, char_name))
    if api_data.get("answer_source") == "enterprise_knowledge_base":
        source_text = "、".join(api_data.get("sources") or [])
        if source_text:
            reply = f"{reply}\n\n【企业知识库来源】{source_text}"
    elif api_data.get("error"):
        reply = f"{reply}\n\n【提示】{api_data['error']}"

    history.append({"role": "user", "content": transcript})
    history.append({"role": "assistant", "content": reply})
    save_user_history(username, char_name, history)

    return (
        history,
        transcript,
        status_markdown(mode, None),
        build_assistant_insights(transcript, mode, voice_style, char_name),
        extract_profile(transcript),
        build_acceptance_panel(True),
        "",
        build_character_card(char_name),
        api_data.get("tts_audio_path"),
        "",
    )


def reset_session(char_name: str = DEFAULT_CHARACTER) -> tuple[list[dict[str, Any]], str, str, str, str, str, str, str]:
    char_name = char_name or DEFAULT_CHARACTER
    c = get_character(char_name)
    msgs = get_welcome_messages(char_name)
    return (
        msgs,
        "",
        status_markdown("日常聊天", None),
        build_assistant_insights("", "日常聊天", c["default_voice"], char_name),
        extract_profile(""),
        build_acceptance_panel(False),
        "",
        build_character_card(char_name),
    )




def build_call_panel(active: bool = False, char_name: str = DEFAULT_CHARACTER) -> str:
    c = get_character(char_name)
    status = "通话中" if active else "待拨号"
    line = "正在自动监听，说话结束后会自动识别并回复" if active else "点击拨打后进入连续语音通话"
    cls = "call-card call-card-active" if active else "call-card"
    route = "XIAOLE-LINE / LIVE"
    return (
        f'<div class="{cls}">'
        f'  <div class="call-line">'
        f'    <span class="call-dot"></span>'
        f'    <div><b>{status}</b><span>{c["name"]} / {c["tag"]}</span></div>'
        f'  </div>'
        f'  <div class="dial-number">{route}</div>'
        f'  <div class="call-meta">{line}</div>'
        f'</div>'
    )


def start_call(char_name: str, history: list[dict[str, Any]] | None) -> tuple[dict[str, Any], str, list[dict[str, Any]], list[dict[str, Any]]]:
    char_name = char_name or DEFAULT_CHARACTER
    c = get_character(char_name)
    history = list(history or get_welcome_messages(char_name))
    history.append({
        "role": "assistant",
        "content": f"{c['name']}已接通。我会自动监听你的声音，说完停顿一下就会识别并回复。",
    })
    state = {"active": True, "char_name": char_name, "started_at": time.time()}
    return state, build_call_panel(True, char_name), history, history


def end_call(char_name: str, history: list[dict[str, Any]] | None) -> tuple[dict[str, Any], str, list[dict[str, Any]], list[dict[str, Any]]]:
    char_name = char_name or DEFAULT_CHARACTER
    c = get_character(char_name)
    history = list(history or get_welcome_messages(char_name))
    history.append({"role": "assistant", "content": f"与{c['name']}的通话已结束。"})
    state = {"active": False, "char_name": char_name, "started_at": None}
    return state, build_call_panel(False, char_name), history, history


def toggle_call(
    char_name: str,
    history: list[dict[str, Any]] | None,
    call_state: dict[str, Any] | None,
    request_obj: gr.Request,
) -> tuple[dict[str, Any], str, list[dict[str, Any]], list[dict[str, Any]], Any]:
    username = get_current_user_from_gradio(request_obj)
    if bool((call_state or {}).get("active")):
        state, panel, new_history, new_chat_state = end_call(char_name, history)
        save_user_history(username, char_name, new_history)
        return state, panel, new_history, new_chat_state, gr.update(value="拨打", variant="primary")

    state, panel, new_history, new_chat_state = start_call(char_name, history)
    save_user_history(username, char_name, new_history)
    return state, panel, new_history, new_chat_state, gr.update(value="挂断", variant="stop")


def reset_workspace(
    char_name: str = DEFAULT_CHARACTER,
    request_obj: Optional[gr.Request] = None,
) -> tuple[list[dict[str, Any]], str, str, str, str, str, str, str, dict[str, Any], str, Any]:
    username = get_current_user_from_gradio(request_obj)
    clear_user_history(username, char_name)
    session = reset_session(char_name)
    new_call_state = {"active": False, "char_name": char_name or DEFAULT_CHARACTER, "started_at": None}
    return (*session, new_call_state, build_call_panel(False, char_name), call_toggle_button_update(new_call_state))


def call_toggle_button_update(call_state: dict[str, Any] | None) -> Any:
    if bool((call_state or {}).get("active")):
        return gr.update(value="挂断", variant="stop")
    return gr.update(value="拨打", variant="primary")


def on_character_change(
    char_name: str,
    call_state: dict[str, Any] | None = None,
    request_obj: Optional[gr.Request] = None,
) -> tuple[Any, str, str, str, str, str, str, str, str, str, dict[str, Any], Any]:
    """切换角色时刷新问候、角色卡、通话面板，并通过 iframe 重载数字人。"""
    char_name = char_name or DEFAULT_CHARACTER
    username = get_current_user_from_gradio(request_obj)
    c = get_character(char_name)
    messages = load_user_history(username, char_name)
    session = (
        messages,
        "",
        status_markdown("日常聊天", None),
        build_assistant_insights("", "日常聊天", c["default_voice"], char_name),
        extract_profile(""),
        build_acceptance_panel(False),
        "",
        build_character_card(char_name),
    )
    active = bool((call_state or {}).get("active"))
    new_call_state = {
        "active": active,
        "char_name": char_name,
        "started_at": (call_state or {}).get("started_at") if active else None,
    }
    viewer_html = build_live2d_viewer(char_name)
    call_panel = build_call_panel(active, char_name)
    return (
        gr.update(value=messages, avatar_images=chatbot_avatar_pair(username, char_name)),
        *session[1:],
        viewer_html,
        call_panel,
        new_call_state,
        call_toggle_button_update(new_call_state),
    )


def load_user_workspace(
    char_name: str = DEFAULT_CHARACTER,
    request_obj: Optional[gr.Request] = None,
) -> tuple[
    Any,
    list[dict[str, Any]],
    str,
    str,
    str,
    str,
    str,
    str,
    str,
    dict[str, Any],
    str,
    Any,
    str,
    str,
    None,
    str,
    str,
    str,
    str,
    Any,
]:
    char_name = char_name or DEFAULT_CHARACTER
    username = get_current_user_from_gradio(request_obj)
    c = get_character(char_name)
    messages = load_user_history(username, char_name)
    new_call_state = {"active": False, "char_name": char_name, "started_at": None}
    profile = load_user_profile(username)
    return (
        gr.update(value=messages, avatar_images=chatbot_avatar_pair(username, char_name)),
        messages,
        "",
        status_markdown("日常聊天", None),
        build_assistant_insights("", "日常聊天", c["default_voice"], char_name),
        extract_profile(""),
        build_acceptance_panel(False),
        "",
        build_character_card(char_name),
        new_call_state,
        build_call_panel(False, char_name),
        call_toggle_button_update(new_call_state),
        gr.update(value=profile.get("nickname") or ""),
        profile.get("gender") or "未设置",
        profile.get("birthday") or "",
        None,
        user_profile_card(profile, compact=True),
        user_profile_card(profile),
        "",
    )


AUTH_DB_PATH = Path(__file__).parent / "xiaole_users.sqlite3"
AUTH_COOKIE_NAME = "xiaole_session"
AUTH_PUBLIC_PATHS = {
    "/login",
    "/register",
    "/auth/logout",
    "/mock/health",
}
MAX_STORED_MESSAGES = 80
GENDER_OPTIONS = ["未设置", "女", "男", "其他"]
ALLOWED_AVATAR_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"}


def init_auth_db() -> None:
    with sqlite3.connect(AUTH_DB_PATH) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                password_salt TEXT NOT NULL,
                active_session TEXT,
                created_at INTEGER NOT NULL,
                last_login_at INTEGER
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS captcha_challenges (
                id TEXT PRIMARY KEY,
                code_hash TEXT NOT NULL,
                expires_at INTEGER NOT NULL,
                used INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS user_memory (
                username TEXT NOT NULL,
                char_name TEXT NOT NULL,
                chat_history TEXT NOT NULL,
                updated_at INTEGER NOT NULL,
                PRIMARY KEY (username, char_name),
                FOREIGN KEY (username) REFERENCES users(username) ON DELETE CASCADE
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS user_profiles (
                username TEXT PRIMARY KEY,
                nickname TEXT,
                gender TEXT,
                birthday TEXT,
                avatar_path TEXT,
                updated_at INTEGER NOT NULL,
                FOREIGN KEY (username) REFERENCES users(username) ON DELETE CASCADE
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_captcha_expires ON captcha_challenges(expires_at)")
        conn.commit()


def hash_password(password: str, salt: str | None = None) -> tuple[str, str]:
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("ascii"), 160_000)
    return digest.hex(), salt


def verify_password(password: str, stored_hash: str, salt: str) -> bool:
    digest, _ = hash_password(password, salt)
    return hmac.compare_digest(digest, stored_hash)


def normalize_username(username: str) -> str:
    return str(username or "").strip().lower()


def captcha_hash(code: str) -> str:
    return hashlib.sha256(code.upper().encode("utf-8")).hexdigest()


def create_captcha() -> tuple[str, str]:
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    code = "".join(secrets.choice(alphabet) for _ in range(4))
    captcha_id = secrets.token_urlsafe(18)
    now = int(time.time())
    with sqlite3.connect(AUTH_DB_PATH) as conn:
        conn.execute("DELETE FROM captcha_challenges WHERE expires_at < ? OR used = 1", (now,))
        conn.execute(
            "INSERT INTO captcha_challenges(id, code_hash, expires_at, used) VALUES (?, ?, ?, 0)",
            (captcha_id, captcha_hash(code), now + 300),
        )
        conn.commit()
    return captcha_id, code


def verify_captcha(captcha_id: str, code: str) -> bool:
    captcha_id = str(captcha_id or "")
    code = str(code or "").strip().upper()
    if not captcha_id or not code:
        return False
    now = int(time.time())
    with sqlite3.connect(AUTH_DB_PATH) as conn:
        row = conn.execute(
            "SELECT code_hash, expires_at, used FROM captcha_challenges WHERE id = ?",
            (captcha_id,),
        ).fetchone()
        if not row:
            return False
        stored_hash, expires_at, used = row
        conn.execute("UPDATE captcha_challenges SET used = 1 WHERE id = ?", (captcha_id,))
        conn.commit()
    return not used and expires_at >= now and hmac.compare_digest(stored_hash, captcha_hash(code))


def captcha_svg(code: str) -> str:
    chars = []
    for index, char in enumerate(code):
        x = 22 + index * 28
        y = 42 + ((index % 2) * 6)
        rotate = [-9, 7, -5, 8][index % 4]
        chars.append(f'<text x="{x}" y="{y}" transform="rotate({rotate} {x} {y})">{html.escape(char)}</text>')
    noise = "".join(
        f'<line x1="{secrets.randbelow(140)}" y1="{secrets.randbelow(56)}" x2="{secrets.randbelow(140)}" y2="{secrets.randbelow(56)}" />'
        for _ in range(8)
    )
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="144" height="56" viewBox="0 0 144 56" role="img" aria-label="图形验证码">
  <rect width="144" height="56" rx="8" fill="#f4fbf8"/>
  <g stroke="#b7d8ce" stroke-width="1" opacity="0.7">{noise}</g>
  <g font-family="Consolas, 'Microsoft YaHei', monospace" font-size="30" font-weight="800" fill="#087158">{''.join(chars)}</g>
</svg>"""


def auth_page(mode: str = "login", error: str = "") -> HTMLResponse:
    captcha_id, code = create_captcha()
    captcha_data = base64.b64encode(captcha_svg(code).encode("utf-8")).decode("ascii")
    is_register = mode == "register"
    action = "/register" if is_register else "/login"
    title = "注册小乐账号" if is_register else "登录小乐"
    submit = "注册并登录" if is_register else "登录"
    switch_href = "/login" if is_register else "/register"
    switch_text = "已有账号，去登录" if is_register else "没有账号，去注册"
    error_html = f'<div class="auth-error">{html.escape(error)}</div>' if error else ""
    html_doc = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{title}</title>
  <style>
    :root {{ --accent:#0e8f70; --accent-strong:#087158; --line:#d9e7e1; --ink:#172522; --muted:#687a74; }}
    * {{ box-sizing: border-box; }}
    body {{ margin:0; min-height:100dvh; display:grid; place-items:center; padding:24px; font-family: "Microsoft YaHei", system-ui, sans-serif; color:var(--ink); background:linear-gradient(180deg,#fbfdfb,#edf6f2); }}
    .auth-card {{ width:min(420px,100%); border:1px solid var(--line); border-radius:8px; background:#fff; padding:26px; box-shadow:0 18px 44px rgba(28,72,61,.12); }}
    .brand {{ display:flex; align-items:center; gap:10px; margin-bottom:18px; }}
    .glyph {{ width:38px; height:38px; border-radius:50%; display:grid; place-items:center; background:var(--accent); color:#fff; font-weight:900; }}
    h1 {{ margin:0; font-size:22px; letter-spacing:0; }}
    p {{ margin:6px 0 22px; color:var(--muted); line-height:1.6; }}
    label {{ display:block; margin:14px 0 7px; font-weight:800; font-size:14px; }}
    input {{ width:100%; min-height:44px; border:1px solid var(--line); border-radius:8px; padding:0 12px; font-size:15px; outline:none; }}
    input:focus {{ border-color:rgba(14,143,112,.64); box-shadow:0 0 0 3px rgba(14,143,112,.12); }}
    .captcha-row {{ display:grid; grid-template-columns:1fr 144px; gap:10px; align-items:center; }}
    .captcha-row img {{ width:144px; height:56px; border:1px solid var(--line); border-radius:8px; background:#f4fbf8; }}
    button {{ width:100%; min-height:44px; margin-top:20px; border:0; border-radius:8px; background:var(--accent); color:#fff; font-size:15px; font-weight:900; cursor:pointer; }}
    button:hover {{ background:var(--accent-strong); }}
    .switch {{ margin-top:16px; text-align:center; }}
    .switch a {{ color:var(--accent-strong); font-weight:800; text-decoration:none; }}
    .auth-error {{ margin:0 0 12px; padding:10px 12px; border:1px solid #ffd3d3; border-radius:8px; background:#fff5f5; color:#a93434; font-size:14px; }}
  </style>
</head>
<body>
  <main class="auth-card">
    <div class="brand"><span class="glyph">乐</span><div><h1>{title}</h1><p>登录后进入小乐语音通话台。</p></div></div>
    {error_html}
    <form method="post" action="{action}">
      <input type="hidden" name="captcha_id" value="{html.escape(captcha_id)}" />
      <label for="username">账号</label>
      <input id="username" name="username" autocomplete="username" required minlength="3" maxlength="32" />
      <label for="password">密码</label>
      <input id="password" name="password" type="password" autocomplete="current-password" required minlength="6" maxlength="72" />
      <label for="captcha_code">图形验证码</label>
      <div class="captcha-row">
        <input id="captcha_code" name="captcha_code" required maxlength="6" autocomplete="off" />
        <img src="data:image/svg+xml;base64,{captcha_data}" alt="图形验证码" />
      </div>
      <button type="submit">{submit}</button>
    </form>
    <div class="switch"><a href="{switch_href}">{switch_text}</a></div>
  </main>
</body>
</html>"""
    return HTMLResponse(html_doc)


def create_user_session(username: str) -> str:
    token = secrets.token_urlsafe(32)
    now = int(time.time())
    with sqlite3.connect(AUTH_DB_PATH) as conn:
        conn.execute(
            "UPDATE users SET active_session = ?, last_login_at = ? WHERE username = ?",
            (token, now, username),
        )
        conn.commit()
    return token


def get_current_user(request: Request) -> str | None:
    token = request.cookies.get(AUTH_COOKIE_NAME)
    if not token:
        return None
    with sqlite3.connect(AUTH_DB_PATH) as conn:
        row = conn.execute("SELECT username FROM users WHERE active_session = ?", (token,)).fetchone()
    return str(row[0]) if row else None


def get_current_user_from_gradio(request_obj: gr.Request | None) -> str | None:
    if request_obj is None:
        return None
    try:
        cookies = dict(getattr(request_obj, "cookies", {}) or {})
    except Exception:
        cookies = {}
    token = cookies.get(AUTH_COOKIE_NAME)
    if not token:
        return None
    with sqlite3.connect(AUTH_DB_PATH) as conn:
        row = conn.execute("SELECT username FROM users WHERE active_session = ?", (token,)).fetchone()
    return str(row[0]) if row else None


def user_session_id(username: str | None) -> str:
    if not username:
        return "gradio-live2d-session"
    digest = hashlib.sha256(username.encode("utf-8")).hexdigest()[:16]
    return f"gradio-user-{digest}"


def static_file_url(path: str | None) -> str | None:
    value = str(path or "").strip()
    if not value:
        return None
    if value.startswith("/static/"):
        return value
    static_root = WEB_STATIC_DIR.resolve()
    try:
        resolved = Path(value).resolve()
        relative = resolved.relative_to(static_root)
    except (OSError, ValueError):
        return None
    return "/static/" + relative.as_posix()


def static_url_to_path(value: str | None) -> str | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    if raw.startswith("/static/"):
        candidate = WEB_STATIC_DIR / raw.removeprefix("/static/")
    else:
        candidate = Path(raw)
    try:
        resolved = candidate.resolve()
    except OSError:
        return None
    return str(resolved) if resolved.exists() and resolved.is_file() else None


def character_avatar_url(char_name: str = DEFAULT_CHARACTER) -> str:
    return str(get_character(char_name or DEFAULT_CHARACTER).get("avatar_image") or "/static/avatars/xiaozhi.svg")


def character_avatar_path(char_name: str = DEFAULT_CHARACTER) -> str:
    return static_url_to_path(character_avatar_url(char_name)) or str(WEB_STATIC_DIR / "avatars" / "xiaozhi.svg")


def default_user_profile(username: str | None) -> dict[str, str]:
    return {
        "username": username or "",
        "nickname": username or "用户",
        "gender": "未设置",
        "birthday": "",
        "avatar_path": "",
        "avatar_url": DEFAULT_USER_AVATAR,
    }


def load_user_profile(username: str | None) -> dict[str, str]:
    profile = default_user_profile(username)
    if not username:
        return profile
    with sqlite3.connect(AUTH_DB_PATH) as conn:
        row = conn.execute(
            "SELECT nickname, gender, birthday, avatar_path FROM user_profiles WHERE username = ?",
            (username,),
        ).fetchone()
    if not row:
        return profile
    nickname, gender, birthday, avatar_path = row
    profile["nickname"] = str(nickname or username)
    profile["gender"] = str(gender or "未设置")
    profile["birthday"] = str(birthday or "")
    profile["avatar_path"] = str(avatar_path or "")
    profile["avatar_url"] = static_file_url(profile["avatar_path"]) or DEFAULT_USER_AVATAR
    return profile


def validate_birthday(value: str) -> str:
    birthday = str(value or "").strip()
    if not birthday:
        return ""
    try:
        datetime.strptime(birthday, "%Y-%m-%d")
    except ValueError as exc:
        raise ValueError("生日格式请使用 YYYY-MM-DD，例如 2003-08-12。") from exc
    return birthday


def save_uploaded_avatar(username: str, avatar_file: Any) -> str | None:
    if not avatar_file:
        return None
    source = Path(str(avatar_file))
    if not source.exists() or not source.is_file():
        return None
    suffix = source.suffix.lower()
    if suffix not in ALLOWED_AVATAR_SUFFIXES:
        raise ValueError("头像只支持 png、jpg、jpeg、gif、webp、svg。")
    USER_AVATAR_DIR.mkdir(parents=True, exist_ok=True)
    safe_username = "".join(ch if ch in string.ascii_lowercase + string.digits + "_-" else "_" for ch in username)
    target = USER_AVATAR_DIR / f"{safe_username}-{secrets.token_hex(6)}{suffix}"
    shutil.copy2(source, target)
    return str(target)


def save_user_profile(
    username: str | None,
    nickname: str,
    gender: str,
    birthday: str,
    avatar_file: Any = None,
) -> tuple[dict[str, str], str]:
    if not username:
        return default_user_profile(None), "请先登录后再保存资料。"
    nickname = str(nickname or "").strip()[:32] or username
    gender = str(gender or "未设置").strip()
    if gender not in GENDER_OPTIONS:
        gender = "未设置"
    try:
        birthday = validate_birthday(birthday)
        avatar_path = save_uploaded_avatar(username, avatar_file)
    except ValueError as exc:
        return load_user_profile(username), str(exc)

    existing = load_user_profile(username)
    stored_avatar = avatar_path or existing.get("avatar_path") or ""
    with sqlite3.connect(AUTH_DB_PATH) as conn:
        conn.execute(
            """
            INSERT INTO user_profiles(username, nickname, gender, birthday, avatar_path, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(username) DO UPDATE SET
                nickname = excluded.nickname,
                gender = excluded.gender,
                birthday = excluded.birthday,
                avatar_path = excluded.avatar_path,
                updated_at = excluded.updated_at
            """,
            (username, nickname, gender, birthday, stored_avatar, int(time.time())),
        )
        conn.commit()
    return load_user_profile(username), "资料已保存。"


def chatbot_avatar_pair(username: str | None, char_name: str = DEFAULT_CHARACTER) -> tuple[str, str]:
    profile = load_user_profile(username)
    user_avatar = static_url_to_path(profile.get("avatar_path")) or static_url_to_path(profile.get("avatar_url")) or str(DEFAULT_USER_AVATAR_PATH)
    return (user_avatar, character_avatar_path(char_name))


def chatbot_avatar_update(username: str | None, char_name: str = DEFAULT_CHARACTER) -> Any:
    return gr.update(avatar_images=chatbot_avatar_pair(username, char_name))


def user_profile_card(profile: dict[str, str], compact: bool = False) -> str:
    nickname = html.escape(profile.get("nickname") or profile.get("username") or "用户")
    username = html.escape(profile.get("username") or "")
    gender = html.escape(profile.get("gender") or "未设置")
    birthday = html.escape(profile.get("birthday") or "未设置")
    avatar_url = html.escape(profile.get("avatar_url") or DEFAULT_USER_AVATAR)
    cls = "current-user-strip" if compact else "user-profile-card"
    return (
        f'<div class="{cls}">'
        f'  <img class="user-profile-avatar" src="{avatar_url}" alt="{nickname}"/>'
        '  <div class="user-profile-meta">'
        f'    <div class="user-profile-name">{nickname}</div>'
        f'    <div class="user-profile-sub">@{username}</div>'
        f'    <div class="user-profile-chips"><span>{gender}</span><span>{birthday}</span></div>'
        "  </div>"
        "</div>"
    )


def load_profile_form(
    char_name: str = DEFAULT_CHARACTER,
    request_obj: Optional[gr.Request] = None,
) -> tuple[Any, str, str, None, str, str, Any]:
    username = get_current_user_from_gradio(request_obj)
    profile = load_user_profile(username)
    return (
        gr.update(value=profile.get("nickname") or ""),
        profile.get("gender") or "未设置",
        profile.get("birthday") or "",
        None,
        user_profile_card(profile, compact=True),
        user_profile_card(profile),
        "",
        chatbot_avatar_update(username, char_name),
    )


def save_profile_form(
    nickname: str,
    gender: str,
    birthday: str,
    avatar_file: Any,
    char_name: str = DEFAULT_CHARACTER,
    request_obj: Optional[gr.Request] = None,
) -> tuple[str, str, str, None, str, str, str, Any]:
    username = get_current_user_from_gradio(request_obj)
    profile, status = save_user_profile(username, nickname, gender, birthday, avatar_file)
    return (
        profile.get("nickname") or "",
        profile.get("gender") or "未设置",
        profile.get("birthday") or "",
        None,
        user_profile_card(profile, compact=True),
        user_profile_card(profile),
        status,
        chatbot_avatar_update(username, char_name),
    )


def sanitize_history(history: list[dict[str, Any]] | None) -> list[dict[str, str]]:
    cleaned: list[dict[str, str]] = []
    for item in list(history or [])[-MAX_STORED_MESSAGES:]:
        if not isinstance(item, dict):
            continue
        role = str(item.get("role") or "")
        if role not in {"user", "assistant", "system"}:
            continue
        content = str(item.get("content") or "")
        cleaned.append({"role": role, "content": content})
    return cleaned


def load_user_history(username: str | None, char_name: str = DEFAULT_CHARACTER) -> list[dict[str, str]]:
    char_name = char_name or DEFAULT_CHARACTER
    if not username:
        return get_welcome_messages(char_name)
    with sqlite3.connect(AUTH_DB_PATH) as conn:
        row = conn.execute(
            "SELECT chat_history FROM user_memory WHERE username = ? AND char_name = ?",
            (username, char_name),
        ).fetchone()
    if not row:
        return get_welcome_messages(char_name)
    try:
        messages = json.loads(row[0])
    except json.JSONDecodeError:
        return get_welcome_messages(char_name)
    cleaned = sanitize_history(messages if isinstance(messages, list) else [])
    return cleaned or get_welcome_messages(char_name)


def save_user_history(username: str | None, char_name: str, history: list[dict[str, Any]] | None) -> None:
    if not username:
        return
    char_name = char_name or DEFAULT_CHARACTER
    cleaned = sanitize_history(history)
    with sqlite3.connect(AUTH_DB_PATH) as conn:
        conn.execute(
            """
            INSERT INTO user_memory(username, char_name, chat_history, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(username, char_name) DO UPDATE SET
                chat_history = excluded.chat_history,
                updated_at = excluded.updated_at
            """,
            (username, char_name, json.dumps(cleaned, ensure_ascii=False), int(time.time())),
        )
        conn.commit()


def clear_user_history(username: str | None, char_name: str) -> None:
    if not username:
        return
    with sqlite3.connect(AUTH_DB_PATH) as conn:
        conn.execute(
            "DELETE FROM user_memory WHERE username = ? AND char_name = ?",
            (username, char_name or DEFAULT_CHARACTER),
        )
        conn.commit()


def auth_redirect() -> RedirectResponse:
    return RedirectResponse("/login", status_code=303)


api = FastAPI(title="小乐 Gradio Mock API")
init_auth_db()
api.mount("/static", StaticFiles(directory=WEB_STATIC_DIR), name="static")
if DIGITAL_HUMAN_DIR.is_dir():
    api.mount("/live2d", StaticFiles(directory=DIGITAL_HUMAN_DIR), name="live2d")


@api.middleware("http")
async def no_cache_for_app(request: Any, call_next: Any) -> Any:
    path = request.url.path
    if path.startswith("/static") or path.startswith("/live2d"):
        return await call_next(request)
    if path not in AUTH_PUBLIC_PATHS and not path.startswith("/api/"):
        if get_current_user(request) is None:
            return auth_redirect()
    response = await call_next(request)
    if path in {"/", ""} or path.startswith("/gradio_api"):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response


@api.get("/login")
def login_page() -> HTMLResponse:
    return auth_page("login")


@api.post("/login")
def login_submit(
    username: str = Form(...),
    password: str = Form(...),
    captcha_id: str = Form(...),
    captcha_code: str = Form(...),
) -> Response:
    username = normalize_username(username)
    if not verify_captcha(captcha_id, captcha_code):
        return auth_page("login", "验证码错误或已过期，请重新输入。")
    with sqlite3.connect(AUTH_DB_PATH) as conn:
        row = conn.execute(
            "SELECT password_hash, password_salt FROM users WHERE username = ?",
            (username,),
        ).fetchone()
    if not row or not verify_password(password, row[0], row[1]):
        return auth_page("login", "账号或密码不正确。")
    token = create_user_session(username)
    response = RedirectResponse("/", status_code=303)
    response.set_cookie(AUTH_COOKIE_NAME, token, httponly=True, samesite="lax", max_age=60 * 60 * 8)
    return response


@api.get("/register")
def register_page() -> HTMLResponse:
    return auth_page("register")


@api.post("/register")
def register_submit(
    username: str = Form(...),
    password: str = Form(...),
    captcha_id: str = Form(...),
    captcha_code: str = Form(...),
) -> Response:
    username = normalize_username(username)
    if not (3 <= len(username) <= 32) or not all(ch in string.ascii_lowercase + string.digits + "_-" for ch in username):
        return auth_page("register", "账号只能使用 3-32 位小写字母、数字、下划线或中划线。")
    if len(password) < 6:
        return auth_page("register", "密码至少需要 6 位。")
    if not verify_captcha(captcha_id, captcha_code):
        return auth_page("register", "验证码错误或已过期，请重新输入。")
    password_hash, salt = hash_password(password)
    try:
        with sqlite3.connect(AUTH_DB_PATH) as conn:
            conn.execute(
                "INSERT INTO users(username, password_hash, password_salt, created_at) VALUES (?, ?, ?, ?)",
                (username, password_hash, salt, int(time.time())),
            )
            conn.commit()
    except sqlite3.IntegrityError:
        return auth_page("register", "这个账号已经被注册了。")
    token = create_user_session(username)
    response = RedirectResponse("/", status_code=303)
    response.set_cookie(AUTH_COOKIE_NAME, token, httponly=True, samesite="lax", max_age=60 * 60 * 8)
    return response


@api.get("/auth/logout")
def logout(request: Request) -> Response:
    token = request.cookies.get(AUTH_COOKIE_NAME)
    if token:
        with sqlite3.connect(AUTH_DB_PATH) as conn:
            conn.execute("UPDATE users SET active_session = NULL WHERE active_session = ?", (token,))
            conn.commit()
    response = RedirectResponse("/login", status_code=303)
    response.delete_cookie(AUTH_COOKIE_NAME)
    return response


@api.get("/live2d-viewer")
def live2d_viewer_page() -> Any:
    html_path = WEB_STATIC_DIR / "live2d-viewer.html"
    return HTMLResponse(html_path.read_text(encoding="utf-8"))


@api.get("/mock/health")
def mock_health() -> dict[str, Any]:
    return {
        "success": True,
        "service": "xiaole-gradio-mock",
        "endpoint": "/mock/voice-chat",
        "fields": [
            "success",
            "request_id",
            "asr_text",
            "reply_text",
            "tts_audio_url",
            "crm",
            "tool_status",
            "timings_ms",
            "trace",
        ],
    }


@api.post("/mock/voice-chat")
async def mock_voice_chat(payload: dict[str, Any]) -> dict[str, Any]:
    return build_mock_api_response(payload)


def noop(*_args: Any) -> None:
    return None


with gr.Blocks(
    title="小乐语音通话台",
    theme=gr.themes.Soft(primary_hue="emerald", neutral_hue="zinc"),
    css=APP_CSS,
    js=APP_BOOT_JS,
) as demo:
    chat_state = gr.State(get_welcome_messages(DEFAULT_CHARACTER))
    call_state = gr.State({"active": False, "char_name": DEFAULT_CHARACTER, "started_at": None})

    with gr.Column(elem_classes=["app-shell"]):
        gr.HTML(
            """
            <section class="call-topbar">
              <div>
                <div class="call-title"><span class="call-glyph">乐</span><span>小乐语音通话台</span></div>
                <div class="call-subline">通话逻辑：xiaole-frame-v4 / 已接入后端</div>
              </div>
            </section>
            """
        )

        with gr.Row(equal_height=True, elem_classes=["workbench-grid"]):
            with gr.Column(scale=3, min_width=310, elem_classes=["rail-card"]):
                gr.HTML('<div class="rail-title">输入区</div>')
                call_panel = gr.HTML(build_call_panel(False, DEFAULT_CHARACTER))
                with gr.Row(elem_classes=["call-action-row"]):
                    call_toggle_btn = gr.Button(
                        "拨打",
                        variant="primary",
                        elem_id="xz-call-toggle",
                        elem_classes=["call-toggle"],
                    )
                audio_input = gr.Audio(
                    label="录制或上传",
                    sources=["microphone", "upload"],
                    type="filepath",
                    interactive=True,
                    elem_id="voice-audio-input",
                )
                gr.HTML(
                    """
                    <div id="xz-mic-meter" class="mic-meter-card">
                      <div class="mic-meter-top">
                        <span class="mic-meter-title">麦克风输入电平</span>
                        <span id="xz-mic-meter-status" class="mic-meter-status">等待</span>
                      </div>
                      <div class="mic-meter-track" aria-label="麦克风输入电平">
                        <div id="xz-mic-meter-fill" class="mic-meter-fill"></div>
                      </div>
                      <div class="mic-meter-bottom">
                        <span id="xz-mic-meter-value" class="mic-meter-value">0%</span>
                        <button id="xz-mic-meter-button" class="mic-meter-button" type="button">开始监听</button>
                      </div>
                    </div>
                    """
                )
                text_input = gr.Textbox(
                    label="文字补充",
                    placeholder="输入一句话，或先拨打再开始对话。",
                    lines=5,
                )
                with gr.Row(elem_classes=["voice-action-row"]):
                    text_reply_voice = gr.Checkbox(
                        value=True,
                        label="文字发送后语音回答",
                    )
                    skip_voice_btn = gr.Button("跳过语音", elem_classes=["skip-voice"])
                gr.HTML(
                    """
                    <div class="reply-guard-card">
                      <span><strong>回复占用状态</strong>：文字/语音回复期间暂停通话录音</span>
                      <span id="xz-reply-guard-status" class="reply-guard-status">可录音</span>
                    </div>
                    """
                )
                with gr.Row():
                    submit_btn = gr.Button("发送", variant="primary", elem_classes=["primary"])
                    clear_btn = gr.Button("清空")
                gr.Examples(
                    examples=[
                        ["小乐你好，我想咨询小乐语音助手怎么接后端。"],
                        ["企业邮箱密码忘了，MFA 手机也丢了，应该怎么重置？"],
                        ["数电票报销被退回了，常见原因和处理步骤是什么？"],
                    ],
                    inputs=[text_input],
                    label="示例输入",
                )

            with gr.Column(scale=5, min_width=420, elem_classes=["stage-card"]):
                gr.HTML('<div class="role-drawer-shell"><button id="xz-role-drawer-toggle" class="role-drawer-toggle" type="button" aria-expanded="false">角色设置</button></div>')
                with gr.Column(elem_classes=["role-toolbar"]):
                    char_select = gr.Radio(
                        CHARACTER_NAMES,
                        value=DEFAULT_CHARACTER,
                        label="角色",
                        interactive=True,
                        elem_classes=["role-select"],
                    )
                    mode = gr.Textbox(
                        value="日常聊天",
                        visible=False,
                        elem_classes=["mode-segment"],
                    )
                    preview_voice_btn = gr.Button("试听音色", elem_classes=["voice-preview-btn"])
                char_card = gr.HTML(build_character_card(DEFAULT_CHARACTER), elem_classes=["role-hidden"])
                live2d_viewer = gr.HTML(build_live2d_viewer())

            with gr.Column(scale=5, min_width=560, elem_classes=["right-card"]):
                current_user_card = gr.HTML(
                    user_profile_card(default_user_profile(None), compact=True)
                )
                with gr.Accordion("用户设置", open=False, elem_classes=["profile-settings"]):
                    profile_card = gr.HTML(user_profile_card(default_user_profile(None)))
                    with gr.Row():
                        profile_nickname = gr.Textbox(
                            label="昵称",
                            placeholder="输入你的昵称",
                            lines=1,
                        )
                        profile_gender = gr.Radio(
                            GENDER_OPTIONS,
                            value="未设置",
                            label="性别",
                            interactive=True,
                        )
                    profile_birthday = gr.Textbox(
                        label="生日",
                        placeholder="YYYY-MM-DD",
                        lines=1,
                    )
                    profile_avatar = gr.File(
                        label="上传头像",
                        file_types=["image"],
                        type="filepath",
                    )
                    save_profile_btn = gr.Button("保存用户设置", variant="primary", elem_classes=["primary"])
                    profile_status = gr.Markdown("", elem_classes=["profile-status"])
                with gr.Tabs():
                    with gr.Tab("聊天窗口"):
                        chatbot = gr.Chatbot(
                            value=get_welcome_messages(DEFAULT_CHARACTER),
                            label="聊天窗口",
                            type="messages",
                            height=900,
                            show_copy_button=True,
                            avatar_images=(str(DEFAULT_USER_AVATAR_PATH), character_avatar_path(DEFAULT_CHARACTER)),
                            elem_classes=["main-chatbot"],
                        )
                    with gr.Tab("信息预览"):
                        transcript_output = gr.Textbox(
                            label="ASR 识别文本",
                            lines=3,
                            interactive=False,
                        )
                        status_panel = gr.Markdown(status_markdown("日常聊天", None))
                        insight_panel = gr.Markdown(build_assistant_insights("", "日常聊天", get_character_voice(DEFAULT_CHARACTER), DEFAULT_CHARACTER))
                        crm_panel = gr.Markdown(extract_profile(""))
                        acceptance_panel = gr.Markdown(build_acceptance_panel(False))
                        reply_audio = gr.Audio(
                            label="回答语音",
                            type="filepath",
                            autoplay=True,
                            interactive=False,
                            visible=True,
                        )
                        stop_reply_audio_btn = gr.Button("跳过语音", elem_classes=["skip-voice"])
                with gr.Group(elem_classes=["hidden-call-bridge"]):
                    call_audio_payload = gr.Textbox(
                        label="通话音频载荷",
                        elem_id="xz-call-audio-payload",
                        lines=1,
                    )
                    call_audio_submit_btn = gr.Button(
                        "提交通话音频",
                        elem_id="xz-call-audio-submit",
                    )

    demo.load(
        load_user_workspace,
        inputs=[char_select],
        outputs=[
            chatbot,
            chat_state,
            transcript_output,
            status_panel,
            insight_panel,
            crm_panel,
            acceptance_panel,
            text_input,
            char_card,
            call_state,
            call_panel,
            call_toggle_btn,
            profile_nickname,
            profile_gender,
            profile_birthday,
            profile_avatar,
            current_user_card,
            profile_card,
            profile_status,
        ],
    )

    save_profile_btn.click(
        save_profile_form,
        inputs=[profile_nickname, profile_gender, profile_birthday, profile_avatar, char_select],
        outputs=[
            profile_nickname,
            profile_gender,
            profile_birthday,
            profile_avatar,
            current_user_card,
            profile_card,
            profile_status,
            chatbot,
        ],
    )

    call_toggle_btn.click(
        toggle_call,
        inputs=[char_select, chat_state, call_state],
        outputs=[call_state, call_panel, chatbot, chat_state, call_toggle_btn],
    ).then(
        noop,
        inputs=[call_state],
        outputs=[],
        js=SYNC_CALL_RECORDING_JS,
    )

    stop_reply_audio_btn.click(
        lambda: None,
        outputs=[reply_audio],
    ).then(noop, outputs=[], js=STOP_SPEECH_JS)

    skip_voice_btn.click(
        lambda: None,
        outputs=[reply_audio],
    ).then(noop, outputs=[], js=STOP_SPEECH_JS)

    preview_voice_btn.click(
        preview_character_voice,
        inputs=[char_select],
        outputs=[reply_audio],
    ).then(
        noop,
        inputs=[text_reply_voice, call_state],
        outputs=[],
        js=PLAY_REPLY_AUDIO_JS,
    )

    submit_btn.click(
        submit_text_message,
        inputs=[text_input, mode, char_select, text_reply_voice, chat_state],
        outputs=[
            chatbot,
            transcript_output,
            status_panel,
            insight_panel,
            crm_panel,
            acceptance_panel,
            text_input,
            char_card,
            reply_audio,
        ],
    ).then(lambda messages: messages, inputs=[chatbot], outputs=[chat_state]).then(
        synthesize_last_assistant_audio,
        inputs=[chatbot, char_select, text_reply_voice],
        outputs=[reply_audio],
    ).then(
        noop,
        inputs=[text_reply_voice, call_state],
        outputs=[],
        js=PLAY_REPLY_AUDIO_JS,
    )

    audio_input.stop_recording(
        submit_message,
        inputs=[audio_input, text_input, mode, char_select, text_reply_voice, chat_state],
        outputs=[
            chatbot,
            transcript_output,
            status_panel,
            insight_panel,
            crm_panel,
            acceptance_panel,
            text_input,
            char_card,
            reply_audio,
        ],
    ).then(lambda messages: messages, inputs=[chatbot], outputs=[chat_state]).then(
        noop,
        inputs=[text_reply_voice, call_state],
        outputs=[],
        js=PLAY_REPLY_AUDIO_JS,
    )

    audio_input.upload(
        submit_message,
        inputs=[audio_input, text_input, mode, char_select, text_reply_voice, chat_state],
        outputs=[
            chatbot,
            transcript_output,
            status_panel,
            insight_panel,
            crm_panel,
            acceptance_panel,
            text_input,
            char_card,
            reply_audio,
        ],
    ).then(lambda messages: messages, inputs=[chatbot], outputs=[chat_state]).then(
        noop,
        inputs=[text_reply_voice, call_state],
        outputs=[],
        js=PLAY_REPLY_AUDIO_JS,
    )

    call_audio_submit_btn.click(
        submit_call_audio,
        inputs=[call_audio_payload, mode, char_select, chat_state],
        outputs=[
            chatbot,
            transcript_output,
            status_panel,
            insight_panel,
            crm_panel,
            acceptance_panel,
            text_input,
            char_card,
            reply_audio,
            call_audio_payload,
        ],
    ).then(lambda messages: messages, inputs=[chatbot], outputs=[chat_state]).then(
        noop,
        inputs=[text_reply_voice, call_state],
        outputs=[],
        js=PLAY_REPLY_AUDIO_JS,
    )

    clear_btn.click(
        reset_workspace,
        inputs=[char_select],
        outputs=[
            chatbot,
            transcript_output,
            status_panel,
            insight_panel,
            crm_panel,
            acceptance_panel,
            text_input,
            char_card,
            call_state,
            call_panel,
            call_toggle_btn,
        ],
    ).then(lambda messages: messages, inputs=[chatbot], outputs=[chat_state]).then(
        noop,
        inputs=[chatbot, char_select, text_reply_voice],
        outputs=[],
        js=SPEAK_LAST_ASSISTANT_JS,
    )

    char_select.change(
        on_character_change,
        inputs=[char_select, call_state],
        outputs=[
            chatbot,
            transcript_output,
            status_panel,
            insight_panel,
            crm_panel,
            acceptance_panel,
            text_input,
            char_card,
            live2d_viewer,
            call_panel,
            call_state,
            call_toggle_btn,
        ],
    ).then(lambda messages: messages, inputs=[chatbot], outputs=[chat_state]).then(
        noop,
        inputs=[chatbot, char_select, text_reply_voice],
        outputs=[],
        js=SPEAK_LAST_ASSISTANT_JS,
    )


if __name__ == "__main__":
    import uvicorn

    demo.queue(default_concurrency_limit=4, max_size=32)
    app = gr.mount_gradio_app(api, demo, path="/")
    uvicorn.run(app, host="127.0.0.1", port=7860)



