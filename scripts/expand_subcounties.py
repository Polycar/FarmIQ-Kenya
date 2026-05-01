import os
import pandas as pd
import requests
import time

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sc_path = os.path.join(BASE_DIR, "data", "subcounties.csv")

# Read existing
existing_df = pd.read_csv(sc_path)
existing_pairs = set(zip(existing_df["County"], existing_df["SubCounty"]))

# All 290 Constituencies (grouped by County)
ALL_CONSTITUENCIES = {
    "Mombasa": ["Changamwe", "Jomvu", "Kisauni", "Nyali", "Likoni", "Mvita"],
    "Kwale": ["Msambweni", "Lunga Lunga", "Matuga", "Kinango"],
    "Kilifi": ["Kilifi North", "Kilifi South", "Kaloleni", "Rabai", "Ganze", "Malindi", "Magarini"],
    "Tana River": ["Garsen", "Galole", "Bura"],
    "Lamu": ["Lamu East", "Lamu West"],
    "Taita Taveta": ["Taveta", "Wundanyi", "Mwatate", "Voi"],
    "Garissa": ["Garissa Township", "Balambala", "Lagdera", "Dadaab", "Fafi", "Ijara"],
    "Wajir": ["Wajir North", "Wajir East", "Wajir South", "Wajir West", "Eldas", "Tarbaj"],
    "Mandera": ["Mandera West", "Mandera Banissa", "Mandera North", "Mandera South", "Mandera East", "Lafey"],
    "Marsabit": ["Moyale", "North Horr", "Saku", "Laisamis"],
    "Isiolo": ["Isiolo North", "Isiolo South"],
    "Meru": ["Igembe South", "Igembe Central", "Igembe North", "Tigania West", "Tigania East", "North Imenti", "Buuri", "Central Imenti", "South Imenti"],
    "Tharaka Nithi": ["Maara", "Chuka Igambang'ombe", "Tharaka"],
    "Embu": ["Manyatta", "Runyenjes", "Mbeere North", "Mbeere South"],
    "Kitui": ["Kitui West", "Kitui Central", "Kitui Rural", "Kitui South", "Kitui East", "Mwingi North", "Mwingi West", "Mwingi Central"],
    "Machakos": ["Masinga", "Yatta", "Kangundo", "Matungulu", "Kathiani", "Mavoko", "Machakos Town", "Mwala"],
    "Makueni": ["Mbooni", "Kilome", "Kaiti", "Makueni", "Kibwezi West", "Kibwezi East"],
    "Nyandarua": ["Kinangop", "Kipipiri", "Ol Kalou", "Ol Jorok", "Ndaragwa"],
    "Nyeri": ["Tetu", "Kieni", "Mathira", "Othaya", "Mukurweini", "Nyeri Town"],
    "Kirinyaga": ["Mwea", "Gichugu", "Ndia", "Kirinyaga Central"],
    "Murang'a": ["Kangema", "Mathioya", "Kiharu", "Kigumo", "Kandara", "Maragua", "Gatanga"],
    "Kiambu": ["Gatundu South", "Gatundu North", "Juja", "Ruiru", "Githunguri", "Kiambu", "Kiambaa", "Kabete", "Kikuyu", "Limuru", "Lari", "Thika Town"],
    "Turkana": ["Turkana North", "Turkana West", "Turkana Central", "Loima", "Turkana South", "Turkana East"],
    "Samburu": ["Samburu North", "Samburu West", "Samburu East"],
    "Trans Nzoia": ["Kwanza", "Endebess", "Saboti", "Kiminini", "Cherangany"],
    "Uasin Gishu": ["Soy", "Turbo", "Moiben", "Ainabkoi", "Kapseret", "Kesses"],
    "Elgeyo Marakwet": ["Marakwet East", "Marakwet West", "Keiyo North", "Keiyo South"],
    "Nandi": ["Tinderet", "Aldai", "Nandi Hills", "Chesumei", "Emgwen", "Mosop"],
    "Baringo": ["Tiaty", "Baringo North", "Baringo Central", "Baringo South", "Mogotio", "Eldama Ravine"],
    "Laikipia": ["Laikipia West", "Laikipia East", "Laikipia North"],
    "Nakuru": ["Molo", "Njoro", "Naivasha", "Gilgil", "Kuresoi South", "Kuresoi North", "Subukia", "Rongai", "Bahati", "Nakuru Town West", "Nakuru Town East"],
    "Narok": ["Narok North", "Narok South", "Narok East", "Narok West", "Emurua Dikirr", "Kilgoris"],
    "Kajiado": ["Kajiado North", "Kajiado Central", "Kajiado East", "Kajiado West", "Kajiado South"],
    "Kericho": ["Kipkelion East", "Kipkelion West", "Ainamoi", "Bureti", "Belgut", "Sigowet-Soin"],
    "Bomet": ["Sotik", "Chepalungu", "Bomet East", "Bomet Central", "Konoin"],
    "Kakamega": ["Lugari", "Likuyani", "Malava", "Lurambi", "Navakholo", "Mumias West", "Mumias East", "Matungu", "Butere", "Khwisero", "Shinyalu", "Ikolomani"],
    "Vihiga": ["Vihiga", "Sabatia", "Hamisi", "Emuhaya", "Luanda"],
    "Bungoma": ["Mt. Elgon", "Sirisia", "Kabuchai", "Bumula", "Kanduyi", "Webuye East", "Webuye West", "Kimilili", "Tongaren"],
    "Busia": ["Teso North", "Teso South", "Nambale", "Matayos", "Butula", "Funyula", "Budalangi"],
    "Siaya": ["Ugenya", "Ugunja", "Alego Usonga", "Gem", "Bondo", "Rarieda"],
    "Kisumu": ["Kisumu East", "Kisumu West", "Kisumu Central", "Seme", "Nyando", "Muhoroni", "Nyakach"],
    "Homa Bay": ["Kasipul", "Kabondo Kasipul", "Karachuonyo", "Rangwe", "Homa Bay Town", "Ndhiwa", "Suba North", "Suba South"],
    "Migori": ["Rongo", "Awendo", "Suna East", "Suna West", "Uriri", "Nyatike", "Kuria East", "Kuria West"],
    "Kisii": ["Bonchari", "South Mugirango", "Bomachoge Borabu", "Bobasi", "Bomachoge Chache", "Nyaribari Chache", "Nyaribari Masaba", "Kitutu Chache North", "Kitutu Chache South"],
    "Nyamira": ["Kitutu Masaba", "West Mugirango", "North Mugirango", "Borabu"],
    "Nairobi": ["Westlands", "Dagoretti North", "Dagoretti South", "Lang'ata", "Kibra", "Roysambu", "Kasarani", "Ruaraka", "Embakasi South", "Embakasi North", "Embakasi Central", "Embakasi East", "Embakasi West", "Makadara", "Kamukunji", "Starehe", "Mathare"],
}

# Resolve coordinates via Nominatim
headers = {"User-Agent": "FarmIQKenyaPrecisionBot/1.0"}

new_rows = []
for county, subcounties in ALL_CONSTITUENCIES.items():
    for sc in subcounties:
        if (county, sc) in existing_pairs:
            continue
            
        print(f"Looking up: {sc}, {county}...")
        url = f"https://nominatim.openstreetmap.org/search?q={sc}+constituency,+Kenya&format=json&limit=1"
        try:
            resp = requests.get(url, headers=headers)
            if resp.status_code == 200 and resp.json():
                data = resp.json()[0]
                lat = float(data["lat"])
                lon = float(data["lon"])
                new_rows.append({"County": county, "SubCounty": sc, "Latitude": lat, "Longitude": lon})
            else:
                # Try fallback search without "constituency"
                url_fb = f"https://nominatim.openstreetmap.org/search?q={sc},+{county},+Kenya&format=json&limit=1"
                resp_fb = requests.get(url_fb, headers=headers)
                if resp_fb.status_code == 200 and resp_fb.json():
                    data = resp_fb.json()[0]
                    lat = float(data["lat"])
                    lon = float(data["lon"])
                    new_rows.append({"County": county, "SubCounty": sc, "Latitude": lat, "Longitude": lon})
                else:
                    print(f"⚠️ Could not resolve: {sc}, {county}")
            time.sleep(1.0) # Nominatim rate limit
        except Exception as e:
            print(f"Error querying {sc}: {e}")
            time.sleep(1.0)

# Append and save
if new_rows:
    new_df = pd.DataFrame(new_rows)
    final_df = pd.concat([existing_df, new_df], ignore_index=True)
    final_df.to_csv(sc_path, index=False)
    print(f"✅ Successfully added {len(new_rows)} new subcounties.")
else:
    print("No new subcounties needed.")
