from utils.predictive_model import predictor
names = ['La Fm 107.5','la Kalle santiago 1','Escape 88.9 Reggaeton','Emisora Bachata Romántica','Merengue Tradicional','Salsa Tropical FM']
for n in names:
    print(n, '->', predictor._infer_station_genre(n))
