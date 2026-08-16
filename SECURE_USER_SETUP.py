from __future__ import annotations

from services.settings import input_path

import argparse
from getpass import getpass

import pandas as pd

from services.security import password_error, set_password
from services.runtime_paths import runtime_root

def _input(): return input_path(runtime_root())


def users() -> list[str]:
    frame = pd.read_excel(_input(), sheet_name="Mail_Listesi")
    return sorted({str(x).strip() for x in frame.get("Web Kullanıcı", []) if str(x).strip() and str(x) != "nan"})


def main() -> None:
    parser = argparse.ArgumentParser(description="Güvenli kullanıcı şifresi oluşturur.")
    parser.add_argument("username", nargs="?")
    parser.add_argument("--permanent", action="store_true", help="İlk girişte değişiklik isteme.")
    args = parser.parse_args()
    known = users()
    username = (args.username or input(f"Kullanıcı adı ({', '.join(known)}): ")).strip()
    if username not in known:
        raise SystemExit("HATA: Kullanıcı Mail_Listesi içindeki Web Kullanıcı alanında bulunamadı.")
    first = getpass("Yeni şifre: ")
    second = getpass("Yeni şifre tekrar: ")
    if first != second:
        raise SystemExit("HATA: Şifreler aynı değil.")
    error = password_error(first)
    if error:
        raise SystemExit("HATA: " + error)
    set_password(username, first, must_change=not args.permanent)
    print(f"BAŞARILI: {username} için güvenli şifre oluşturuldu.")


if __name__ == "__main__":
    main()
