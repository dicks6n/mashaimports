"""Load real Chinese wholesale markets, categories, products and location passes.

Coordinates and addresses are approximate (good to street level) — verify
them before relying on them for buyer trips.

    python manage.py seed_data
"""

from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from catalog.data import CATEGORIES, CITIES, EXTRA_MARKETS, EXTRA_PRODUCT_MARKETS, EXTRA_PRODUCTS
from catalog.models import Category, Market, Product
from sourcing.models import Plan
from travel.models import City, Service

MARKETS = [
    {
        "name": "Yiwu International Trade City",
        "cats": "toys home jewellery hardware beauty",
        "name_zh": "义乌国际商贸城",
        "city": "Yiwu", "province": "Zhejiang",
        "specialty": "Small commodities · everything under one roof",
        "summary": "The largest small-commodity wholesale market on earth — five districts and tens of thousands of booths.",
        "description": "Spread across five interconnected districts, Yiwu International Trade City supplies toys, "
        "jewellery, stationery, hardware, kitchenware, festive goods and household items to buyers from over 200 "
        "countries. Most booths are factory showrooms, so prices are close to ex-works and MOQs are negotiable.",
        "established": 2002, "booths": 75000, "opening_hours": "09:00 – 17:00 daily",
        "address": "Chouzhou North Road, Futian Subdistrict, Yiwu, Zhejiang",
        "address_zh": "浙江省义乌市福田街道稠州北路",
        "latitude": "29.334600", "longitude": "120.107400",
        "nearest_transit": "Yiwu Railway Station, 20 min by taxi; Yiwu Airport, 15 min",
        "insider_tips": "District 1 (toys, flowers, jewellery) is busiest before 11am. District 5 holds imported goods. "
        "Ask for the booth's factory card — reorders direct to the factory are usually 5–10% cheaper.",
        "image_query": "Yiwu International Trade City", "featured": True,
    },
    {
        "name": "Huaqiangbei Electronics Market",
        "cats": "electronics",
        "name_zh": "华强北电子市场",
        "city": "Shenzhen", "province": "Guangdong",
        "specialty": "Consumer electronics, components & accessories",
        "summary": "Shenzhen's legendary electronics district — phones, components, gadgets and accessories by the thousand.",
        "description": "Huaqiangbei is a square kilometre of electronics malls including SEG Plaza, Huaqiang Electronics "
        "World and Mingtong Digital City. From individual resistors to finished Bluetooth speakers, drones and "
        "phone accessories, it is the fastest place on earth to prototype and buy electronics.",
        "established": 1988, "booths": 30000, "opening_hours": "09:30 – 18:00 daily",
        "address": "Huaqiang North Road, Futian District, Shenzhen, Guangdong",
        "address_zh": "广东省深圳市福田区华强北路",
        "latitude": "22.545000", "longitude": "114.086400",
        "nearest_transit": "Metro Line 1/2/3/7 — Huaqiang Road or Huaqiang North station",
        "insider_tips": "Upper floors of SEG Plaza hold components; finished goods sit in Huaqiang Electronics World. "
        "Always request a working sample and test it before paying a deposit.",
        "image_query": "Huaqiangbei Shenzhen", "featured": True,
    },
    {
        "name": "Baima Clothing Market",
        "cats": "apparel",
        "name_zh": "白马服装市场",
        "city": "Guangzhou", "province": "Guangdong",
        "specialty": "Mid-to-high-end fashion & womenswear",
        "summary": "Guangzhou's premium garment wholesale tower opposite the main railway station.",
        "description": "Baima (White Horse) is one of China's most famous clothing wholesale buildings, hosting brands "
        "and designer studios selling womenswear, menswear and occasion wear. Quality is a step above typical "
        "wholesale and many stalls accept private-label orders.",
        "established": 1993, "booths": 2000, "opening_hours": "08:30 – 18:00 daily",
        "address": "16 Zhanqian Road, Yuexiu District, Guangzhou, Guangdong",
        "address_zh": "广东省广州市越秀区站前路16号",
        "latitude": "23.148900", "longitude": "113.256500",
        "nearest_transit": "Metro Line 2/5 — Guangzhou Railway Station",
        "insider_tips": "Floors 2–4 have the strongest womenswear. Many stalls only sell by the colour-size pack — ask for 'mixed pack' pricing.",
        "image_query": "Guangzhou Railway Station Zhanqian Road clothing", "featured": True,
    },
    {
        "name": "Shisanhang Clothing Wholesale Market",
        "cats": "apparel",
        "name_zh": "十三行服装批发市场",
        "city": "Guangzhou", "province": "Guangdong",
        "specialty": "Fast fashion & affordable apparel",
        "summary": "Historic Thirteen Hongs trading quarter turned fast-fashion wholesale hub.",
        "description": "On the site of the historic Thirteen Factories, Shisanhang's malls (New China Building and others) "
        "turn out new styles weekly at budget-friendly prices. It is the go-to market for boutique owners chasing trends.",
        "established": 1990, "booths": 8000, "opening_hours": "06:00 – 17:00 daily",
        "address": "Shisanhang Road, Liwan District, Guangzhou, Guangdong",
        "address_zh": "广东省广州市荔湾区十三行路",
        "latitude": "23.116700", "longitude": "113.260300",
        "nearest_transit": "Metro Line 1/6 — Huangsha or Cultural Park station",
        "insider_tips": "Arrive by 7am — the best new styles sell out by lunch. Bring a porter for bulk bags.",
        "image_query": "Shisanhang Guangzhou", "featured": False,
    },
    {
        "name": "Guihuagang Leather Goods Market",
        "cats": "bags",
        "name_zh": "桂花岗皮具城",
        "city": "Guangzhou", "province": "Guangdong",
        "specialty": "Handbags, luggage & leather goods",
        "summary": "Dozens of leather-goods malls in Sanyuanli — Asia's biggest bag wholesale cluster.",
        "description": "Guihuagang and the surrounding Sanyuanli streets house thousands of handbag, wallet, belt and "
        "luggage suppliers. Genuine-leather workshops and PU-bag factories show catalogues and take OEM orders.",
        "established": 1995, "booths": 6000, "opening_hours": "09:00 – 18:00 daily",
        "address": "Guihuagang, Sanyuanli Avenue, Baiyun District, Guangzhou, Guangdong",
        "address_zh": "广东省广州市白云区三元里大道桂花岗",
        "latitude": "23.157800", "longitude": "113.261000",
        "nearest_transit": "Metro Line 2 — Sanyuanli station",
        "insider_tips": "Ask to see the material swatch book — the same bag is often offered in 3–4 leather grades.",
        "image_query": "Sanyuanli Guangzhou leather market", "featured": True,
    },
    {
        "name": "Lecong International Furniture City",
        "cats": "furniture",
        "name_zh": "乐从国际家具城",
        "city": "Foshan", "province": "Guangdong",
        "specialty": "Furniture & interior décor",
        "summary": "A 5 km strip of furniture showrooms — the world's largest furniture trading centre.",
        "description": "Lecong in Shunde lines Highway 325 with gigantic showroom towers covering sofas, beds, office, "
        "outdoor and hotel furniture. Factories are nearby, so custom sizes and fabrics are routine.",
        "established": 1980, "booths": 5000, "opening_hours": "09:00 – 18:00 daily",
        "address": "Highway 325, Lecong Town, Shunde District, Foshan, Guangdong",
        "address_zh": "广东省佛山市顺德区乐从镇325国道",
        "latitude": "22.960200", "longitude": "113.084000",
        "nearest_transit": "Foshan Metro Line 3 — Lecong station; 45 min from Guangzhou",
        "insider_tips": "Showroom prices are retail-ish; always ask for the 'container price' and factory visit.",
        "image_query": "Lecong furniture Foshan", "featured": True,
    },
    {
        "name": "Guzhen Lighting Expo",
        "cats": "lighting",
        "name_zh": "古镇灯饰城",
        "city": "Zhongshan", "province": "Guangdong",
        "specialty": "Lighting, chandeliers & LED",
        "summary": "China's lighting capital — around 70% of the country's lamps come from this town.",
        "description": "Guzhen Town in Zhongshan is lined with lighting malls such as Star Alliance and Huayi Plaza. "
        "Crystal chandeliers, architectural LED, smart bulbs and outdoor fittings are all sold factory-direct.",
        "established": 1999, "booths": 3000, "opening_hours": "09:00 – 18:00 daily",
        "address": "Guzhen Town, Zhongshan, Guangdong",
        "address_zh": "广东省中山市古镇镇",
        "latitude": "22.611000", "longitude": "113.190000",
        "nearest_transit": "Guzhen Railway Station (Guangzhou–Zhuhai line)",
        "insider_tips": "Check CE/UL certification sheets before ordering — many shops stock both certified and domestic versions.",
        "image_query": "Guzhen Zhongshan lighting", "featured": False,
    },
    {
        "name": "Liwan Plaza Jewellery Market",
        "cats": "jewellery",
        "name_zh": "荔湾广场",
        "city": "Guangzhou", "province": "Guangdong",
        "specialty": "Fashion jewellery, beads & accessories",
        "summary": "Multi-storey mall of jewellery, hair accessories, beads and gift items.",
        "description": "Liwan Plaza and the neighbouring Changshou Road streets supply costume jewellery, hair accessories, "
        "jade, beads and craft supplies in volume, with many workshops offering custom logo charms.",
        "established": 1997, "booths": 1500, "opening_hours": "09:00 – 18:00 daily",
        "address": "Liwan Plaza, Changshou Road, Liwan District, Guangzhou, Guangdong",
        "address_zh": "广东省广州市荔湾区长寿路荔湾广场",
        "latitude": "23.120600", "longitude": "113.248800",
        "nearest_transit": "Metro Line 1 — Changshou Lu station",
        "insider_tips": "Ground floor is retail; go upstairs for true wholesale and better MOQs.",
        "image_query": "Liwan Plaza Guangzhou", "featured": False,
    },
    {
        "name": "Zhongda Fabric Market",
        "cats": "textiles",
        "name_zh": "中大布匹市场",
        "city": "Guangzhou", "province": "Guangdong",
        "specialty": "Fabrics, textiles & trims",
        "summary": "Asia's biggest fabric market — tens of thousands of fabrics, lace, buttons and trims.",
        "description": "Spread around Sun Yat-sen University in Haizhu, the Zhongda market is where garment factories "
        "buy cotton, silk, denim, lace, zips and trims by the roll. Sampling cuts are available at most stalls.",
        "established": 1985, "booths": 20000, "opening_hours": "08:00 – 18:00 daily",
        "address": "Ruikang Road, Haizhu District, Guangzhou, Guangdong",
        "address_zh": "广东省广州市海珠区瑞康路",
        "latitude": "23.095100", "longitude": "113.292400",
        "nearest_transit": "Metro Line 8 — Kecun or Lujiang station",
        "insider_tips": "Bring a reference swatch; stall owners can match colour and weight from photos within a day.",
        "image_query": "Zhongda fabric market Guangzhou", "featured": False,
    },
    {
        "name": "Yide Road Toy & Gift Market",
        "cats": "toys food",
        "name_zh": "一德路玩具精品市场",
        "city": "Guangzhou", "province": "Guangdong",
        "specialty": "Toys, gifts, party & festive goods",
        "summary": "Historic wholesale street for toys, stationery, party supplies and dried goods.",
        "description": "Yide Road near the Shishi Sacred Heart Cathedral is packed with toy, gift, stationery and "
        "seasonal decoration wholesalers, plus Guangzhou's famous dried seafood street.",
        "established": 1980, "booths": 4000, "opening_hours": "08:00 – 18:00 daily",
        "address": "Yide Road, Yuexiu District, Guangzhou, Guangdong",
        "address_zh": "广东省广州市越秀区一德路",
        "latitude": "23.118900", "longitude": "113.267800",
        "nearest_transit": "Metro Line 6 — Yide Lu station",
        "insider_tips": "Toys exported to the EU/US need EN71 / ASTM test reports — ask before you negotiate price.",
        "image_query": "Yide Road Guangzhou", "featured": False,
    },
    {
        "name": "Dafen Oil Painting Village",
        "cats": "art",
        "name_zh": "大芬油画村",
        "city": "Shenzhen", "province": "Guangdong",
        "specialty": "Hand-painted art & frames",
        "summary": "Village of studios producing hand-painted canvases and custom frames for the world.",
        "description": "Dafen in Longgang has hundreds of studios and galleries producing original and reproduction oil "
        "paintings, canvas prints and frames for hotels, interior designers and retailers.",
        "established": 1989, "booths": 1200, "opening_hours": "09:00 – 21:00 daily",
        "address": "Dafen Village, Buji Street, Longgang District, Shenzhen, Guangdong",
        "address_zh": "广东省深圳市龙岗区布吉街道大芬村",
        "latitude": "22.611900", "longitude": "114.139400",
        "nearest_transit": "Metro Line 3 — Dafen station",
        "insider_tips": "Commission a painting from a photo — typical turnaround is 5–7 days including drying.",
        "image_query": "Dafen oil painting village", "featured": False,
    },
    {
        "name": "Luohu Commercial City",
        "cats": "jewellery bags apparel",
        "name_zh": "罗湖商业城",
        "city": "Shenzhen", "province": "Guangdong",
        "specialty": "Watches, bags, tailoring & accessories",
        "summary": "Five-storey mall at the Hong Kong border — tailoring, watches and accessories.",
        "description": "Directly above Luohu border crossing, this mall is famous for fast custom tailoring, watches, "
        "handbags, sunglasses and electronics accessories in small quantities.",
        "established": 1994, "booths": 1500, "opening_hours": "10:00 – 22:00 daily",
        "address": "Renmin South Road, Luohu District, Shenzhen, Guangdong",
        "address_zh": "广东省深圳市罗湖区人民南路",
        "latitude": "22.532600", "longitude": "114.117300",
        "nearest_transit": "Metro Line 1 — Luohu station; Luohu border crossing",
        "insider_tips": "Great for samples and small runs; for bulk orders the same items are cheaper in Guangzhou.",
        "image_query": "Luohu Commercial City", "featured": False,
    },
    {
        "name": "Qipu Road Clothing Market",
        "cats": "apparel",
        "name_zh": "七浦路服装市场",
        "city": "Shanghai", "province": "Shanghai",
        "specialty": "Wholesale clothing & shoes",
        "summary": "Shanghai's largest clothing wholesale district, a short walk from the Bund.",
        "description": "Qipu Road's buildings hold thousands of stalls selling men's, women's and children's clothing and "
        "footwear, serving retailers across East China.",
        "established": 1980, "booths": 5000, "opening_hours": "07:00 – 17:00 daily",
        "address": "Qipu Road, Jing'an District, Shanghai",
        "address_zh": "上海市静安区七浦路",
        "latitude": "31.247600", "longitude": "121.481900",
        "nearest_transit": "Metro Line 8/10 — Tiantong Road or North Sichuan Road station",
        "insider_tips": "Mornings are wholesale-only at some buildings; afternoons open to retail and prices go up.",
        "image_query": "Qipu Road Shanghai", "featured": False,
    },
    {
        "name": "Jingdezhen Ceramics Market",
        "cats": "home art",
        "name_zh": "景德镇陶瓷市场",
        "city": "Jingdezhen", "province": "Jiangxi",
        "specialty": "Porcelain, ceramics & tableware",
        "summary": "The porcelain capital of China — 1,000 years of kilns, studios and wholesale.",
        "description": "Jingdezhen's Taoxichuan and ceramics markets sell porcelain tableware, vases, tea sets and "
        "hand-painted artware, from mass production to master-made pieces, with custom glazes and logos available.",
        "established": 1004, "booths": 3000, "opening_hours": "09:00 – 18:00 daily",
        "address": "Taoxichuan, Zhushan District, Jingdezhen, Jiangxi",
        "address_zh": "江西省景德镇市珠山区陶溪川",
        "latitude": "29.290600", "longitude": "117.206300",
        "nearest_transit": "Jingdezhen North high-speed rail station, 25 min by taxi",
        "insider_tips": "Ask about breakage allowance and export-grade packing — fragile goods need double-walled cartons.",
        "image_query": "Jingdezhen porcelain market", "featured": True,
    },
]

PRODUCTS = [
    ("True Wireless Earbuds", 0, ["huaqiangbei"], 3.80, 18.00, "200 pcs", "7–15 days", True,
     "Bluetooth 5.3 TWS earbuds with charging case; custom logo and retail box available.", "wireless earbuds"),
    ("Smartwatch & Fitness Bands", 0, ["huaqiangbei", "luohu"], 6.50, 35.00, "100 pcs", "10–20 days", True,
     "Heart-rate, SpO2 and notification smartwatches with OEM app support.", "smartwatch"),
    ("Power Banks & Chargers", 0, ["huaqiangbei", "yiwu-international-trade"], 2.20, 14.00, "300 pcs", "7–15 days", False,
     "10,000–20,000 mAh power banks, GaN fast chargers and cables, CE/FCC available.", "power bank charger"),
    ("Drones & Camera Accessories", 0, ["huaqiangbei"], 12.00, 160.00, "50 pcs", "10–25 days", False,
     "Entry-level camera drones, gimbals, tripods and lighting kits.", "quadcopter drone"),
    ("Women's Dresses (Private Label)", 1, ["baima", "shisanhang", "qipu"], 4.50, 28.00, "50 pcs / style", "10–20 days", True,
     "Trend-led dresses with custom labels, hang-tags and polybag packing.", "women dresses clothing store"),
    ("Men's Casual Wear", 1, ["shisanhang", "qipu", "baima"], 3.20, 20.00, "60 pcs / style", "10–20 days", False,
     "T-shirts, polos, chinos and jackets in mixed size packs.", "men clothing store"),
    ("Sneakers & Footwear", 1, ["qipu", "yiwu-international-trade"], 6.00, 32.00, "120 pairs", "20–35 days", True,
     "Casual sneakers, slides and sandals with custom outsole logos.", "sneakers shoes"),
    ("Genuine Leather Handbags", 2, ["guihuagang", "luohu"], 12.00, 85.00, "50 pcs", "20–30 days", True,
     "Cowhide totes, crossbody and clutch bags with branded hardware.", "leather handbag"),
    ("Travel Luggage Sets", 2, ["guihuagang", "yiwu-international-trade"], 18.00, 70.00, "50 sets", "20–30 days", False,
     "PC/ABS spinner suitcases in 3-piece sets, TSA locks optional.", "suitcase luggage"),
    ("Upholstered Sofas", 3, ["lecong-international"], 180.00, 1200.00, "1 × 40ft container", "25–40 days", True,
     "Fabric and leather sofas with custom sizes, foam density and fabrics.", "sofa furniture"),
    ("Hotel & Office Furniture", 3, ["lecong-international"], 60.00, 900.00, "Project based", "30–45 days", False,
     "Full fit-outs for hotels, offices and restaurants from one supplier cluster.", "office furniture"),
    ("Crystal Chandeliers", 4, ["guzhen"], 45.00, 900.00, "10 pcs", "15–30 days", True,
     "K9 crystal and modern brass chandeliers with CE/UL options.", "crystal chandelier"),
    ("LED Panels & Bulbs", 4, ["guzhen", "yiwu-international-trade"], 0.35, 12.00, "1,000 pcs", "10–20 days", False,
     "Energy-efficient LED bulbs, panels and strip lights.", "LED light bulbs"),
    ("Porcelain Dinnerware Sets", 5, ["jingdezhen", "yiwu-international-trade"], 8.00, 65.00, "100 sets", "25–35 days", True,
     "Bone china and porcelain dinner sets, custom decals and gift boxes.", "porcelain dinnerware"),
    ("Kitchenware & Cookware", 5, ["yiwu-international-trade"], 0.80, 25.00, "300 pcs", "15–25 days", False,
     "Non-stick pans, utensils, storage containers and gadgets.", "kitchen utensils cookware"),
    ("Tea Sets & Ceramic Décor", 5, ["jingdezhen"], 6.00, 120.00, "50 sets", "20–30 days", False,
     "Hand-painted tea sets, vases and ceramic home décor.", "Chinese tea set porcelain"),
    ("Fashion Jewellery", 6, ["liwan", "yiwu-international-trade"], 0.15, 6.00, "500 pcs", "7–15 days", True,
     "Stainless steel and alloy necklaces, rings and earrings, custom charms.", "fashion jewelry necklace"),
    ("Hair Accessories", 6, ["liwan", "yiwu-international-trade"], 0.08, 2.50, "1,000 pcs", "7–15 days", False,
     "Claw clips, scrunchies, headbands and bridal hair pieces.", "hair accessories"),
    ("Cotton & Linen Fabrics", 7, ["zhongda"], 1.20, 9.00, "100 m", "5–15 days", False,
     "Woven cotton, linen and blends by the metre, dyed to Pantone.", "fabric rolls"),
    ("Lace, Trims & Zippers", 7, ["zhongda"], 0.05, 3.00, "500 m", "5–10 days", False,
     "Lace, ribbons, buttons, YKK-style zips and garment trims.", "lace fabric trim"),
    ("Educational & STEM Toys", 8, ["yide", "yiwu-international-trade"], 1.20, 18.00, "200 pcs", "15–25 days", True,
     "Building blocks, puzzles, wooden toys and STEM kits with EN71 reports.", "wooden toys"),
    ("Party & Festive Supplies", 8, ["yide", "yiwu-international-trade"], 0.05, 4.00, "1,000 pcs", "10–20 days", False,
     "Balloons, banners, Christmas décor and seasonal gifts.", "party balloons decorations"),
    ("Hand-Painted Oil Paintings", 9, ["dafen"], 15.00, 400.00, "5 pcs", "7–14 days", True,
     "Original and reproduction oil paintings on canvas, framed or rolled.", "oil painting canvas gallery"),
    ("Picture Frames & Canvas Prints", 9, ["dafen", "yiwu-international-trade"], 1.50, 40.00, "100 pcs", "10–20 days", False,
     "Wood and PS frames, stretched canvas prints for retail and hotels.", "picture frames"),
]

PLANS = [
    ("Explorer Pass", "explorer", "29.00", 7, False, 1, "Planning a single buying trip",
     "Exact addresses for every market\nInteractive maps & Amap / Google links\nNearest metro & transit\n7 days of access"),
    ("Trader Pass", "trader", "79.00", 30, True, 2, "For active importers",
     "Everything in Explorer\nInsider buying tips per market\nPriority WhatsApp support\n30 days of access"),
    ("Partner Pass", "partner", "490.00", 365, False, 3, "Year-round sourcing teams",
     "Everything in Trader\n10% off every sourcing fee (applied by agent)\nQuarterly market reports\n365 days of access"),
]


SERVICES = [
    # slug, name, icon, price, unit, max qty, summary
    ("interpreter", "Market Interpreter & Guide", "译", "120.00", "per day", 14,
     "A bilingual buyer who walks the market with you, translates and negotiates."),
    ("factory-audit", "Factory Visit & Audit", "厂", "180.00", "per factory", 10,
     "We visit the factory, check licences, capacity and working conditions, and send a photo report."),
    ("quality-inspection", "Pre-shipment Quality Inspection", "检", "150.00", "per inspection", 10,
     "AQL inspection before you pay the balance: counts, measurements, function tests and photos."),
    ("supplier-check", "Supplier Verification", "证", "40.00", "per supplier", 20,
     "Business-licence and export-record check to make sure a supplier is real."),
    ("airport-pickup", "Airport / Station Pickup", "接", "60.00", "per transfer", 6,
     "Private car with an English-speaking driver from the airport or train station to your hotel."),
    ("hotel-booking", "Hotel Booking Concierge", "宿", "25.00", "per booking", 5,
     "Tell us your dates and budget; we book a hotel near your markets and send the confirmation."),
    ("visa-letter", "Business Visa Invitation Letter", "签", "80.00", "per traveller", 6,
     "An invitation letter from a registered Chinese company to support your business visa (M visa)."),
    ("canton-fair", "Canton Fair Escort", "展", "150.00", "per day", 10,
     "Fair badge registration help, a guide inside the halls and supplier follow-up."),
    ("product-photos", "Product Photography", "摄", "90.00", "per product", 20,
     "Studio photos of your samples, white-background and lifestyle, ready for your shop."),
    ("sample-consolidation", "Sample Consolidation & Forwarding", "样", "35.00", "per shipment", 10,
     "We collect samples from several suppliers and send them to you in one express parcel."),
]


class Command(BaseCommand):
    help = "Seed markets, cities, categories, products, services and location passes."

    @transaction.atomic
    def handle(self, *args, **opts):
        cats = {}
        for i, (key, name, tagline, query) in enumerate(CATEGORIES):
            cats[key], _ = Category.objects.update_or_create(
                slug=key, defaults={"name": name, "tagline": tagline, "order": i, "image_query": query}
            )

        markets = {}
        for i, data in enumerate(MARKETS):
            data = dict(data)
            keys = data.pop("cats").split()
            for key in ("latitude", "longitude"):
                data[key] = Decimal(data[key])
            obj, _ = Market.objects.update_or_create(name=data.pop("name"), defaults={**data, "order": i})
            obj.categories.set([cats[k] for k in keys])
            markets[obj.slug] = obj

        for i, (name, zh, city, prov, keys, specialty, summary, address, lat, lon) in enumerate(EXTRA_MARKETS):
            obj, _ = Market.objects.update_or_create(
                name=name,
                defaults={
                    "name_zh": zh, "city": city, "province": prov, "specialty": specialty, "summary": summary,
                    "description": f"{summary} {name} is a key sourcing destination for {specialty.lower()} "
                    f"in {city}, {prov}. Our agents compare several stalls here before recommending a supplier.",
                    "address": f"{address}, {city}, {prov}", "latitude": Decimal(str(lat)),
                    "longitude": Decimal(str(lon)), "image_query": f"{name} {city}", "order": 100 + i,
                },
            )
            obj.categories.set([cats[k] for k in keys.split()])
            markets[obj.slug] = obj

        def match(fragments):
            return [m for slug, m in markets.items() if any(f in slug for f in fragments)]

        index_keys = [c[0] for c in CATEGORIES]
        for name, ci, mkeys, pf, pt, moq, lead, featured, summary, query in PRODUCTS:
            self._product(name, cats[index_keys[ci]], match(mkeys + EXTRA_PRODUCT_MARKETS.get(name, [])),
                          pf, pt, moq, lead, featured, summary, query)
        for name, key, mkeys, pf, pt, moq, lead, featured, summary, query in EXTRA_PRODUCTS:
            self._product(name, cats[key], match(mkeys), pf, pt, moq, lead, featured, summary, query)

        for name, (zh, trip_id) in CITIES.items():
            pins = [m for m in markets.values() if m.city == name]
            if not pins:
                continue
            City.objects.update_or_create(
                name=name,
                defaults={
                    "name_zh": zh, "province": pins[0].province, "trip_city_id": trip_id,
                    "latitude": sum(m.latitude for m in pins) / len(pins),
                    "longitude": sum(m.longitude for m in pins) / len(pins),
                },
            )

        for i, (slug, name, icon, price, unit, max_qty, summary) in enumerate(SERVICES):
            Service.objects.update_or_create(
                slug=slug,
                defaults={"name": name, "name_zh": icon, "price": Decimal(price), "unit": unit,
                          "max_quantity": max_qty, "summary": summary, "order": i},
            )

        for name, slug, price, days, hl, order, tagline, features in PLANS:
            Plan.objects.update_or_create(
                slug=slug,
                defaults={"name": name, "price": Decimal(price), "duration_days": days, "highlighted": hl,
                          "order": order, "tagline": tagline, "features": features},
            )

        self.stdout.write(self.style.SUCCESS(
            f"Seeded {len(markets)} markets, {City.objects.count()} cities, {len(cats)} categories, "
            f"{Product.objects.count()} products, {len(SERVICES)} services, {len(PLANS)} passes."
        ))
        self.stdout.write("Next: python manage.py fetch_images   then   python manage.py sync_hotels")

    def _product(self, name, category, markets, pf, pt, moq, lead, featured, summary, query):
        product, _ = Product.objects.update_or_create(
            name=name,
            defaults={
                "category": category, "summary": summary,
                "description": summary + " Our agents compare at least three suppliers in the market, "
                "inspect samples, negotiate price and arrange freight to your door.",
                "price_from": Decimal(str(pf)), "price_to": Decimal(str(pt)),
                "moq": moq, "lead_time": lead, "featured": featured, "image_query": query,
            },
        )
        product.markets.set(markets)
