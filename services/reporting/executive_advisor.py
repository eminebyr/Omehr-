from __future__ import annotations
import pandas as pd

def advise(store: pd.DataFrame, title_df: pd.DataFrame) -> list[str]:
    out=[]
    if store.empty: return ['Analiz için mağaza verisi bulunamadı.']
    top=store.sort_values('Norm Eksiği',ascending=False).iloc[0]
    out.append(f"En yüksek mağaza açığı {top['Mağaza']} mağazasında: {int(top['Norm Eksiği'])} kişi.")
    if not title_df.empty:
        t=title_df.groupby('Unvan',dropna=False)['Norm Eksiği'].sum().sort_values(ascending=False)
        if len(t): out.append(f"Şirket genelinde en kritik unvan {t.index[0]}: {int(t.iloc[0])} kişilik açık.")
    transferable=int(store['Norm Fazlası'].sum()); deficit=int(store['Norm Eksiği'].sum())
    out.append(f"Teorik olarak {min(transferable,deficit)} açık transfer havuzuyla değerlendirilebilir; kalan ihtiyaç işe alım planına aktarılmalıdır.")
    risk=store[store['Norm Eksiği']>=5]
    out.append(f"5 ve üzeri açığı bulunan {len(risk)} kritik mağaza öncelikli aksiyon gerektiriyor.")
    return out
