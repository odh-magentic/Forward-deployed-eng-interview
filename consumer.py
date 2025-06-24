from kafka import KafkaConsumer
import json

consumer = KafkaConsumer(
    "ais_positions",
    bootstrap_servers=["localhost:9092"],
    value_deserializer=lambda m: json.loads(m.decode("utf-8")),
)

for message in consumer:
    ais_data = message.value
    print(f"Vessel {ais_data['mmsi']}: {ais_data['lat']}, {ais_data['lon']}")
