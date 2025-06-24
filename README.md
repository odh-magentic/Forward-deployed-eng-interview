# Synthetic Signal Generator

A comprehensive synthetic data generator for maritime shipping analytics, designed for the "Zero‑to‑Dashboard" interview scenario. This project generates realistic synthetic data streams including AIS vessel positions, port congestion data, weather alerts, geopolitical news, and supplier-vessel mappings.

## Features

- **AIS Vessel Stream**: High-throughput Kafka stream (~12,000 messages/second) with vessel positions and movement data
- **Port Congestion API**: REST endpoint providing real-time port congestion metrics
- **Weather Alerts**: NOAA-style severe weather RSS feed
- **Geopolitical News**: RSS feed with shipping-relevant geopolitical events
- **Supplier Mapping**: Nightly CSV refresh of supplier-to-vessel relationships

## Prerequisites

- Python 3.8+ (tested with 3.12.9)
- Docker and Docker Compose (for Kafka infrastructure)
- At least 4GB RAM available for Kafka

## Quick Start

### 1. Clone and Setup Environment

```bash
git clone <repository-url>
cd forward-deployed-eng-interview

# Using rye (recommended)
rye sync

# Or using pip
pip install -r requirements.lock
```

### 2. Start Kafka Infrastructure

```bash
# Start Kafka and Zookeeper
docker-compose up -d

# Verify Kafka is running
docker-compose ps
```

### 3. Run the Signal Generator

```bash
# Start the synthetic signal generator
uvicorn synthetic_signals:app --reload

# Or run directly
python synthetic_signals.py
```

The application will start on `http://localhost:8000` and begin generating synthetic data immediately.

### 4. Test the Consumer (Optional)

```bash
# In a separate terminal, test the Kafka consumer
python consumer.py
```

## API Endpoints

Once running, the following endpoints are available:

- **Health Check**: `GET /healthz`
- **Port Congestion**: `GET /port_congestion` - JSON array of port congestion data
- **Weather RSS**: `GET /rss/weather` - XML RSS feed of severe weather alerts
- **Geopolitical RSS**: `GET /rss/geopolitics` - XML RSS feed of geopolitical news
- **Supplier Mapping**: `GET /supplier_mapping?n=100` - JSON array of supplier-vessel mappings

### Example API Usage

```bash
# Check application health
curl http://localhost:8000/healthz

# Get port congestion data
curl http://localhost:8000/port_congestion

# Get weather alerts (RSS XML)
curl http://localhost:8000/rss/weather

# Get first 50 supplier mappings
curl "http://localhost:8000/supplier_mapping?n=50"
```

## Data Streams

### AIS Messages (Kafka Topic: `ais_positions`)

```json
{
  "mmsi": 367123456,
  "imo": 9123456,
  "lat": 37.7749,
  "lon": -122.4194,
  "sog": 12.5,
  "cog": 180.0,
  "timestamp": "2024-01-15T10:30:00Z"
}
```

### Port Congestion Data

```json
[
  {
    "port": "Shanghai",
    "queued_vessels": 45,
    "avg_wait_hours": 18.5,
    "updated_at": "2024-01-15T10:30:00Z"
  }
]
```

## Configuration

Configure the application using environment variables:

### Kafka Settings
```bash
export KAFKA_BOOTSTRAP_SERVERS=localhost:9092
export KAFKA_AIS_TOPIC=ais_positions
export AIS_MSGS_PER_SEC=12000
```

### Refresh Intervals
```bash
export PORT_REFRESH_SEC=900          # Port congestion refresh (15 min)
export WEATHER_REFRESH_SEC=900       # Weather feed refresh (15 min)
export NEWS_REFRESH_SEC=1800         # News feed refresh (30 min)
```

### Supplier Table Settings
```bash
export SUPPLIER_TABLE_PATH=supplier_vessel_mapping.csv
export SUPPLIER_TABLE_ROWS=100000
export SUPPLIER_TABLE_REFRESH_HOURS=24
```

## Development

### Project Structure

```
├── synthetic_signals.py      # Main application
├── consumer.py              # Example Kafka consumer
├── docker-compose.yml       # Kafka infrastructure
├── pyproject.toml          # Python dependencies
└── README.md               # This file
```

### Running in Development Mode

```bash
# Start with auto-reload
uvicorn synthetic_signals:app --reload --log-level debug

# Monitor Kafka topics
docker exec -it <kafka-container> kafka-console-consumer.sh \
  --bootstrap-server localhost:9092 \
  --topic ais_positions \
  --from-beginning
```

### Scaling Configuration

For higher throughput testing:

```bash
# Increase AIS message rate
export AIS_MSGS_PER_SEC=50000

# Increase supplier table size
export SUPPLIER_TABLE_ROWS=1000000

# Faster refresh cycles
export PORT_REFRESH_SEC=60
```

## Troubleshooting

### Common Issues

1. **Kafka Connection Failed**
   ```bash
   # Check if Kafka is running
   docker-compose ps
   
   # Restart Kafka services
   docker-compose down && docker-compose up -d
   ```

2. **High Memory Usage**
   ```bash
   # Reduce message rate
   export AIS_MSGS_PER_SEC=1000
   
   # Reduce supplier table size
   export SUPPLIER_TABLE_ROWS=10000
   ```

3. **Port Already in Use**
   ```bash
   # Run on different port
   uvicorn synthetic_signals:app --port 8001
   ```

### Monitoring

- **Application Logs**: Check uvicorn output for errors
- **Kafka Logs**: `docker-compose logs kafka`
- **Resource Usage**: Monitor CPU/memory with `docker stats`

## Production Considerations

- Use dedicated Kafka cluster instead of Docker Compose
- Implement proper logging and monitoring
- Add authentication and rate limiting
- Configure persistent storage for Kafka
- Set up proper error handling and alerting

## License

This project is for interview purposes and internal use only.
