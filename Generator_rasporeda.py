import pandas as pd
import streamlit as st
import numpy as np
from typing import List, Dict
#-----------------------------------------
#               ALGORITAM
#-----------------------------------------
def pretvori_vrijeme_u_broj(time_str) -> int:
    if ":" in time_str:
        hours, minutes = map(int, time_str.strip().split(":"))
        return hours * 100 + minutes
    else:
        return int(time_str.strip())

def grupiraj_uzastopne_smjene(smjene):
    if not smjene:
        return []
    
    grupe_smjena = []
    trenutna_grupa = [smjene[0]]
    
    for smjena in smjene[1:]:
        prethodna_smjena = trenutna_grupa[-1]
        if (smjena["Sat"] == prethodna_smjena["Sat"] + 1 and
            smjena["Lokacija"] == prethodna_smjena["Lokacija"] and
            smjena["Zona rada"] == prethodna_smjena["Zona rada"]):
            trenutna_grupa.append(smjena)
        else:
            grupe_smjena.append(trenutna_grupa)
            trenutna_grupa = [smjena]
    
    grupe_smjena.append(trenutna_grupa)
    return grupe_smjena

def je_li_raspored_valjan(zaposlenik: pd.Series,dan: str,sat: int,trenutni_raspored: Dict[str, Dict[str, List[Dict[str, str]]]]):
    if dan not in zaposlenik["Dani dostupnosti"].split(", "):
        return False

    pocetni_sat, zavrsni_sat = map(
        pretvori_vrijeme_u_broj, zaposlenik["Raspon sati dostupnosti"].split("-")
    )
    if sat * 100 < pocetni_sat or sat * 100 >= zavrsni_sat:
        return False

    if zaposlenik["Ime"] in trenutni_raspored:
        if dan in trenutni_raspored[zaposlenik["Ime"]]:
            dnevni_sati = len(trenutni_raspored[zaposlenik["Ime"]][dan])
            if dnevni_sati >= zaposlenik["Maksimalni sati dnevno"]:
                return False

        ukupni_sati = sum(
            len(sati) for sati in trenutni_raspored[zaposlenik["Ime"]].values()
        )
        if ukupni_sati >= zaposlenik["Maksimalni sati"]:
            return False

    for emp, emp_raspored in trenutni_raspored.items():
        if dan in emp_raspored:
            for sat_data in emp_raspored[dan]:
                if sat_data["Sat"] == sat:
                    if sat_data["Lokacija"] in zaposlenik["Lokacija"].split(
                        ", "
                    ) and sat_data["Zona rada"] in zaposlenik["Zona rada"].split(", "):
                        return False
    return True


def heuristicki_odaberi_zaposlenika(
    zaposlenici: pd.DataFrame,
    trenutni_raspored: Dict[str, Dict[str, List[int]]],
    dan: str,
    sat: int
    ):
    zaposlenici_kopija = zaposlenici.copy()

    for index, zaposlenik in zaposlenici_kopija.iterrows():
        if zaposlenik["Ime"] in trenutni_raspored:
            ukupni_sati = sum(
                len(sati) for sati in trenutni_raspored[zaposlenik["Ime"]].values()
            )
            zaposlenici_kopija.at[index, "Preostali sati"] = (
                zaposlenik["Maksimalni sati"] - ukupni_sati
            )
        else:
            zaposlenici_kopija.at[index, "Preostali sati"] = zaposlenik["Maksimalni sati"]

        if dan not in zaposlenik["Dani dostupnosti"].split(", ") or not je_li_raspored_valjan(
            zaposlenik, dan, sat, trenutni_raspored
        ):
            zaposlenici_kopija.at[index, "Dostupan"] = False
        else:
            zaposlenici_kopija.at[index, "Dostupan"] = True

    zaposlenici_sortirani = zaposlenici_kopija[zaposlenici_kopija["Dostupan"]].sort_values(
        by=["Prioritet", "Preostali sati", "Minimalni sati"],
        ascending=[False, False, False],
    )

    if zaposlenici_sortirani.empty:
        return None
    return zaposlenici_sortirani.iloc[0]


def backtrack(
    zaposlenici: pd.DataFrame,
    raspored: Dict[str, Dict[str, List[Dict[str, str]]]],
    dan: str,
    sat: int,
    ):
    if sat == 24:
        return True

    zaposlenik = heuristicki_odaberi_zaposlenika(zaposlenici, raspored, dan, sat)

    if zaposlenik is not None and je_li_raspored_valjan(zaposlenik, dan, sat, raspored):
        if zaposlenik["Ime"] not in raspored:
            raspored[zaposlenik["Ime"]] = {}
        if dan not in raspored[zaposlenik["Ime"]]:
            raspored[zaposlenik["Ime"]][dan] = []

        lokacije = zaposlenik["Lokacija"].split(", ")
        zone = zaposlenik["Zona rada"].split(", ")

        for lokacija in lokacije:
            for zona in zone:
                raspored[zaposlenik["Ime"]][dan].append(
                    {"Sat": sat, "Lokacija": lokacija, "Zona rada": zona}
                )

                if backtrack(zaposlenici, raspored, dan, sat + 1):
                    return True

                raspored[zaposlenik["Ime"]][dan].pop()

        if len(raspored[zaposlenik["Ime"]][dan]) == 0:
            del raspored[zaposlenik["Ime"]][dan]
        if len(raspored[zaposlenik["Ime"]]) == 0:
            del raspored[zaposlenik["Ime"]]

    return backtrack(zaposlenici, raspored, dan, sat + 1)

def stvori_optimalni_raspored(zaposlenici: pd.DataFrame):
    dani = ["Ponedjeljak", "Utorak", "Srijeda", "Četvrtak", "Petak", "Subota", "Nedjelja"]
    raspored = {}

    for dan in dani:
        backtrack(zaposlenici, raspored, dan, 0)

    podaci_rasporeda = []
    for zaposlenik, dani_dict in raspored.items():
        for dan, sati_list in dani_dict.items():
            if isinstance(sati_list, list) and all(isinstance(item, dict) for item in sati_list):
                sati_sortirani = sorted(sati_list, key=lambda x: x["Sat"])
                
                for smjena in grupiraj_uzastopne_smjene(sati_sortirani):
                    podaci_rasporeda.append({
                        "Ime": zaposlenik,
                        "Dan": dan,
                        "Radno vrijeme": f"{smjena[0]['Sat']:02d}:00 - {smjena[-1]['Sat'] + 1:02d}:00",
                        "Vrsta posla": zaposlenici.loc[zaposlenici["Ime"] == zaposlenik, "Vrsta posla"].values[0],
                        "Lokacija": smjena[0].get("Lokacija", "Nepoznato"),
                        "Zona rada": smjena[0].get("Zona rada", "Nepoznato")
                    })
            else:
                print(f"Upozorenje: Neočekivana struktura za zaposlenika {zaposlenik} na dan {dan}")

    return pd.DataFrame(podaci_rasporeda)

stupci = [
    "Ime",
    "Vrsta posla",
    "Minimalni sati",
    "Maksimalni sati",
    "Maksimalni sati dnevno",
    "Dani dostupnosti",
    "Raspon sati dostupnosti",
    "Lokacija",
    "Zona rada",
    "Prioritet"
]

if "df" not in st.session_state:
    st.session_state.df = pd.DataFrame(columns=stupci)
#-----------------------------------------
#               STREAMLIT
#-----------------------------------------
st.title("Sustav za unos zaposlenika i parametara rasporeda")
st.subheader("Unesite informacije o zaposlenicima za generiranje optimalnog rasporeda.")

with st.form("employee_form", clear_on_submit=True):
    st.header("Podaci o zaposleniku")

    ime_zaposlenika = st.text_input("Ime zaposlenika", placeholder="Unesite ime i prezime")
    vrsta_posla_zaposlenika = st.selectbox(
        "Vrsta posla",
        ["Konobar", "Kuhar", "Čistač", "Dostavljač", "Slastičar", "Ostalo"],
    )

    minimalni_sati_tjedno = st.number_input(
        "Minimalni sati rada tjedno", min_value=0, max_value=168, value=20, step=1
    )
    maksimalni_sati_tjedno = st.number_input(
        "Maksimalni sati rada tjedno", min_value=0, max_value=168, value=40, step=1
    )
    maksimalni_sati_dnevno = st.number_input(
        "Maksimalni sati rada dnevno", min_value=1, max_value=24, value=8, step=1
    )

    st.subheader("Dostupnost zaposlenika")
    dostupni_dani = st.multiselect(
        "Dostupni dani za rad",
        options=["Ponedjeljak", "Utorak", "Srijeda", "Četvrtak", "Petak", "Subota", "Nedjelja",],
        default=["Ponedjeljak", "Utorak", "Srijeda", "Četvrtak", "Petak"],
    )
    raspon_dostupnosti = st.slider(
        "Raspon sati dostupnosti",
        min_value=0,
        max_value=24,
        value=(8, 16),
        step=1,
        format="%d:00"
    )
    st.subheader("Lokacija zaposlenja")
    lokacije_rada = st.multiselect("Lokacija", options=["Kafić A", "Kafić B", "Kafić C"])

    zone_rada = st.multiselect("Zona rada", options=["Terasa", "Unutra", "Šank"])

    st.subheader("Preferencije poslodavca")
    prioritet_zaposlenika = st.selectbox(
        "Prioritet zaposlenika u rasporedu", ["Nizak", "Srednji", "Visok"], index=1
    )
    podneseno = st.form_submit_button("Dodaj zaposlenika")
    if podneseno:
        novi_redak = {
            "Ime": ime_zaposlenika,
            "Vrsta posla": vrsta_posla_zaposlenika,
            "Minimalni sati": minimalni_sati_tjedno,
            "Maksimalni sati": maksimalni_sati_tjedno,
            "Maksimalni sati dnevno": maksimalni_sati_dnevno,
            "Dani dostupnosti": ", ".join(dostupni_dani),
            "Raspon sati dostupnosti": f"{raspon_dostupnosti[0] * 100:04d} - {raspon_dostupnosti[1] * 100:04d}",
            "Lokacija": ", ".join(lokacije_rada),
            "Zona rada": ", ".join(zone_rada),
            "Prioritet": prioritet_zaposlenika
        }
        novi_df = pd.DataFrame([novi_redak])
        st.session_state.df = pd.concat(
            [st.session_state.df, novi_df], ignore_index=True
        )

        st.success(f"Zaposlenik '{ime_zaposlenika}' uspješno dodan!")

st.write("**Trenutni popis zaposlenika:**")
st.dataframe(st.session_state.df)

if st.button("Generiraj", type="primary"):
    df_zaposlenika = pd.DataFrame(st.session_state.df)

    optimalni_raspored = stvori_optimalni_raspored(df_zaposlenika)

    for dan in ["Ponedjeljak", "Utorak", "Srijeda", "Četvrtak", "Petak", "Subota","Nedjelja"]:
        st.subheader(dan)
        dnevni_raspored = optimalni_raspored[optimalni_raspored["Dan"] == dan]
        if not dnevni_raspored.empty:
            st.dataframe(
                dnevni_raspored[["Ime", "Radno vrijeme", "Vrsta posla", "Lokacija", "Zona rada"]]
            )
        else:
            st.write("Nema rasporeda za ovaj dan.")

