from __future__ import annotations

"""Kök seviyesi ince yeniden-dışa-aktarım — gerçek uygulama `tools/verify_release.py`.

Önceden bu dosya `tools/verify_release.py`'nin BİREBİR KOPYASIYDI (iki ayrı
kaynak, sessizce birbirinden ayrışma riski taşıyordu). Kopyalanan modül
düzeyi `ROOT = Path(__file__).resolve().parents[1]` satırı, bu dosya proje
KÖKÜNDE olduğu için proje kökünün BİR ÜSTÜNÜ işaret ediyordu — kullanılmayan
ama gerçek bir tuzaktı. Artık tek kaynak `tools/verify_release.py`'dir.
"""

from tools.verify_release import (
    ROOT,
    SECRET_PATTERNS,
    TEXT_SUFFIXES,
    main,
    run_checked,
    run_pytest_isolated,
    secret_scan,
    sha256,
    verify,
)

__all__ = [
    "ROOT",
    "SECRET_PATTERNS",
    "TEXT_SUFFIXES",
    "main",
    "run_checked",
    "run_pytest_isolated",
    "secret_scan",
    "sha256",
    "verify",
]

if __name__ == "__main__":
    raise SystemExit(main())
