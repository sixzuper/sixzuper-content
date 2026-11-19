# SOP — SixZuper Labs Instagram auto-publish (Instagram Login)

**Status: CRON HARIAN AKTIF; PRODUCER SUDAH BERJALAN.** Per 2026-11-19, Hermes mencatat 29 run producer harian; queue menandai slot 08.00 dan 13.00 tanggal itu `published` serta slot 19.00 `scheduled`. Status queue bukan pengganti Meta readback. Bukti satu slot terjadwal yang dibaca balik independen pada 2026-10-21: media `17983651094899112`, permalink `https://www.instagram.com/p/Devtvl8AZPL/`. Jadwal producer `ce641f86c6f1` aktif pukul 05.15 WIB dan publisher `79f62bd026fc` pada 08.00/13.00/19.00 WIB.

## Sasaran dan batas
- Tiga slot maksimal per hari: **08.00, 13.00, 19.00 WIB**; unik `YYYYMMDD-slot`, tidak menumpuk post lama ke slot baru.
- Tema rotasi SixZuper; fokus perjalanan STB → Mini PC/Proxmox. Jumat berita hanya jika URL sumber asli dan klaim penting lolos verifikasi; jika tidak, **skip + alert**, bukan mengarang.
- Konten selesai = **draft valid → JPEG 1080×1350 lolos QA → URL HTTPS publik lolos GET/MIME/hash → antrean `scheduled` → pemicu slot → Meta `media_publish` → readback ID/permalink/caption akun @sixzuper → `published`**. Telegram draft, Git push, container ID, atau exit 0 bukan bukti publish.
- Maksimum satu post per slot. Hijau/rutin senyap; masalah dan perbaikan nyata hanya ke Telegram `#cronjobs` (`-1003924559518`, thread `416`). Tidak mengirim secret atau URL OAuth ke Telegram/Git/log.

## Kondisi awal (audit 2026-10-21)
- Hermes cron `0ac8f6006e1e` pukul 05.00 WIB hanya menghasilkan **teks tiga draft ke topic draft**. Tidak menulis queue/gambar, tidak membuat jadwal IG.
- Root `queue.json`: 36 `draft_ready`, 0 `scheduled`, tidak ada draft_ready dengan gambar publik. Draft lama jangan langsung dijadwalkan massal; beberapa entri historis `published` mempunyai ID `dry-run` palsu.
- Runner `scripts/ig_daily_publish.py` saat ini aman terhadap dry-run tetapi **berbicara dengan Facebook Graph**, sedangkan token Page Facebook kini 190/463. **Jangan aktifkan cron untuk runner ini.**
- Token Instagram Login yang diizinkan pemilik **sudah terpasang privat** di `~/.hermes/.env` (mode `0600`); pembacaan balik `/me`, `/me/media`, dan `/content_publishing_limit` cocok dengan `@sixzuper`. Refresh live di `graph.instagram.com/refresh_access_token` berhasil; token baru diverifikasi sebelum penulisan atomik, `expires_in` Meta dicatat sebagai `IG_INSTAGRAM_LOGIN_EXPIRES_AT` (2026-12-20 02:24 UTC). Job watchdog `ef736417ec1e` pukul 03.10 WIB diam saat aman dan refresh pada umur ≥30 hari. Kredensial Git remote sudah dikeluarkan dari URL; credential helper diverifikasi membaca remote. Ini belum membuktikan job publish 13.00 berhasil.

## Pemeriksaan cepat (read-only)
```bash
cd ~/sixzuper-content && .venv/bin/python3 scripts/ig_autopublish_preflight.py
```
`PASS/BLOCK` per gerbang; exit `2` bila belum siap. Pada audit awal: `NOT_READY` karena token IG Login dan metadata expiry belum terpasang, antrean terjadwal kosong, job publisher/producer belum ada, dan remote Git masih mengandung kredensial dalam URL. `READY` dari preflight pun **bukan** pengganti bukti satu slot yang terbit lewat scheduler dan Graph readback.

## Tahap implementasi dan gerbang

### 1. Kredensial dan host API — WAJIB sebelum cron
1. Pa Ricky memasukkan **Instagram Login long-lived token yang baru/valid** melalui prompt tersembunyi SSH; jangan copy token dari OCR screenshot. Simpan di `~/.hermes/.env` mode `0600`, nama `IG_INSTAGRAM_LOGIN_TOKEN`, tanpa menimpa `IG_ACCESS_TOKEN` jalur Facebook. Jangan commit, cetak, atau masukkan token ke argumen shell.
2. Verifikasi `GET https://graph.instagram.com/v24.0/me?fields=id,user_id,username,account_type` memakai bearer token; wajib `user_id` cocok `IG_USER_ID`, `username=sixzuper`, akun profesional. Uji baca `/me/media` dan izin publish melalui satu post uji terkontrol; jangan berasumsi hanya dari awalan IGAAT.
3. Meta menyatakan token dari **App Dashboard** long-lived sekitar 60 hari; validasi asal dan umur token. Catat `issued_at`, `expires_at` hasil nyata, bukan estimasi berdasarkan screenshot. Token Business Login short-lived (sekitar 1 jam) harus ditukar di sisi server dengan secret Instagram App yang benar. Jika umur/refresh tidak dapat dibuktikan, **jangan pasang jadwal unattended**.
4. Pekerjaan refresh tersendiri: bila long-lived berumur ≥24 jam dan belum expired, `GET https://graph.instagram.com/refresh_access_token?grant_type=ig_refresh_token&access_token=...`; verifikasi token hasil via `/me`, tulis `.env` atomik (backup 0600), catat expiry. Jalankan pemeriksaan harian; refresh misalnya pada umur ≥30 hari, alert jauh sebelum 60 hari. Jika 190/expired, berhenti dan minta reauth; jangan melanjutkan publish.

### 2. Produksi → antrean (idempotent)
1. Job 05.00 menghasilkan tiga **record terstruktur** (tanggal+slot, tema, caption feed, teks kartu, sumber bila Jumat), bukan hanya pesan Telegram. Pertahankan prompt/gaya yang disetujui. Validasi panjang, fakta teknis, branding, hashtag, sumber, slot unik, dan larangan URL/hasil fiktif. Kegagalan satu item → `review_required` + alert, bukan konten placeholder.
2. Render kartu lokal 1080×1350 **JPEG standar** untuk kompatibilitas dokumentasi Meta (PNG pernah berhasil dalam smoke test tetapi jangan dijadikan jaminan format). QA dimensi, MIME, legibilitas, clipping, kontras, serta teks yang akurat. Jika QA gagal, tahan item.
3. Stage **hanya** file media tujuan (bukan `git add -A`); remote Git bersih dari PAT di URL, otentikasi privat. Push dan bandingkan commit lokal vs remote. GET URL raw/CDN publik; verifikasi HTTP 200, JPEG, dan hash dengan file lokal. Jangan mengandalkan URL placeholder (`placehold.co`).
4. Simpan queue dengan lock dan tulis atomik: `draft_ready → media_ready → scheduled`, `post_time` ISO timezone `+07:00`; hanya slot mendatang; jangan mengonversi 36 draft historis otomatis. Jika slot terlewat, `review_required`/skip, bukan publish dadakan.

### 3. Publisher terjadwal (setelah tahap 1+2 lolos)
1. Satu scheduler durable menjalankan skrip publisher pada **08.00/13.00/19.00 WIB**. Pastikan timezone aktual scheduler `Asia/Jakarta`, tidak menganggap cron UTC. Keluaran hijau kosong. Jangan memasang beberapa scheduler yang memanggil publisher sama.
2. Ambil tepat satu item `scheduled` jatuh tempo untuk slotnya. Lock global, validasi akun, token, caption, URL gambar, CDN dan kuota. Sebelum POST, cari posting terakhir pada Meta dengan marker unik (misalnya `#SZPYYYYMMDDHH`) untuk mencegah duplikat. Simpan `container_id` + status attempt secara atomik.
3. `POST /{IG_USER_ID}/media` pada `graph.instagram.com`; poll `status_code` sampai `FINISHED` (batas wajar). `POST /{IG_USER_ID}/media_publish` **sekali**. Jika timeout/respons ambigu: cek media terbaru dan pending state; **jangan retry publish secara buta**.
4. `GET /{media_id}?fields=id,caption,permalink,timestamp,media_type`. Baru set queue `published` ketika ID, akun, marker, dan permalink cocok. Tulis log tanpa token. Error auth/CDN/publish → queue tetap belum published, alert ke `#cronjobs`; tidak ada pesan sukses hijau.

### 4. Bukti penerimaan sebelum status “otomatis aktif”
- Dry-run lokal tanpa POST: tiga slot terstruktur, tiga media QA, tiga URL publik benar, tiga `scheduled` mendatang; tidak menulis `published`.
- Satu slot nyata **tanpa perintah publish manual** dari produksi sampai readback permalink Instagram, dengan log cron (waktu trigger, job ID), queue, dan ID media unik. Jangan menyebut otomatis sebelum bukti ini ada.
- Tes negatif: token invalid/expired, CDN 404, gambar bukan JPEG, sumber Jumat invalid, dua runner serentak, timeout setelah POST, item tertinggal. Semua harus fail closed tanpa duplikat dan alert tepat sasaran.
- Tes token refresh/expiry dan restart gateway/mesin: jadwal tetap ada, token tetap privat, tidak ada replay/backfill yang tak diminta.

## Implementasi harian (crons aktif; ilustrasi AI menunggu kuota)
- `scripts/ig_generate_daily_login.py` meminta tepat tiga draft JSON, memvalidasi caption/kartu/slot, lalu meminta tiga ilustrasi topik berbeda sebelum menyiapkan JPEG/antrean. Cron producer `ce641f86c6f1` berjalan 05.15 WIB; publisher `79f62bd026fc` berjalan 08/13/19 WIB. 29 run hingga 19 Nov terjadi sebelum integrasi AI image ini memakai kartu lama; queue hari itu menandai 08/13 `published`, 19 `scheduled` (queue bukan bukti Meta readback). Resume: draft dan ilustrasi matching dipakai ulang; antrean parsial/berbeda ditolak. Jumat tetap diblokir sampai verifikasi sumber tersedia.
- Jumat **sengaja ditahan** dengan error/alert sampai pemeriksaan fakta artikel terhadap isi sumber tersedia. HTTP 200 pada URL berita bukan bukti klaim caption benar. Jangan melabeli sistem 7 hari penuh sebelum gerbang ini teratasi.

## Gambar AI (terhubung ke producer; provider belum tersedia)
- Producer `ig_generate_daily_login.py` kini meminta tiga ilustrasi topik dari `ig_ai_illustration.py`, menambahkan teks/logo lokal, dan meneruskan hanya tiga gambar valid/berbeda ke renderer/CDN/queue. Cache PNG dan metadata disimpan privat `data/ig-ai-generated` (dir 0700, file 0600); percobaan gagal tidak membuat slot terjadwal atau mengganti diam-diam dengan kartu generik. Jadwal/publisher tidak diubah.
- Uji satu gambar nyata lokal 2026-11-19 gagal HTTP 429 dari Google Gemini `RESOURCE_EXHAUSTED`; tool gambar Hermes juga gagal HTTP 400 karena model tidak didukung pada autentikasi Codex ini. Karena itu belum ada ilustrasi nyata, queue AI-image, atau post AI-image yang terverifikasi. Produser harian berikutnya yang tidak tertahan gerbang Jumat akan gagal tertutup hingga kuota gambar tersedia. Slot tanggal 19 Nov pukul 19.00 yang sudah terjadwal tidak diubah dan masih memakai aset lama.
- Setelah kuota/provider aktif: jalankan satu preview lokal tanpa upload/queue/Meta: `.venv/bin/python3 scripts/ig_ai_illustration.py --draft content/ig-slot-proof-20261021-13.json --output-dir /tmp/ig-preview`; inspeksi visual hasil, lalu uji batch tiga ilustrasi dan baca balik URL/CDN sebelum klaim pipeline aktif. Jangan lakukan publish manual sebagai substitusi uji cron.

## Rollback
- Pause **hanya** cron publisher dan job produksi IG terkait bila ada duplikat/klaim sukses palsu; job monitoring/backup lain tidak disentuh. Simpan queue, pending state, media ID, dan log untuk audit. Jangan hapus post IG yang sudah terbit tanpa izin Pa Ricky.
- Jika token bermasalah, hentikan publish, perbaiki jalur auth secara privat, uji read-only dan satu controlled post lagi; baru resume scheduler.

## Referensi resmi Meta
- [Business Login for Instagram — token long-lived & refresh](https://developers.facebook.com/docs/instagram-platform/instagram-api-with-instagram-login/business-login)
- [Get started — App Dashboard token](https://developers.facebook.com/docs/instagram-platform/instagram-api-with-instagram-login/get-started)
- [Content Publishing — host, izin, dua tahap, limit](https://developers.facebook.com/docs/instagram-platform/instagram-api-with-instagram-login/content-publishing)
