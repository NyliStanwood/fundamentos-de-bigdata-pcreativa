import json
from kafka import KafkaConsumer, TopicPartition

# Connect to Kafka
consumer = KafkaConsumer(
    bootstrap_servers=['localhost:9092'],
    auto_offset_reset='earliest',
    value_deserializer=lambda m: m.decode('utf-8') if m else None
)

# Assign to the response topic
consumer.assign([TopicPartition('flight-delay-ml-response', 0)])
consumer.seek_to_beginning()

print("Messages in 'flight-delay-ml-response' topic:")
print("=" * 60)

message_count = 0
target_id = '25a51571-a20d-4509-ad39-1e224e457115'

for message in consumer:
    message_count += 1
    try:
        data = json.loads(message.value)
        print(f"\nMessage {message_count}:")
        print(json.dumps(data, indent=2))
        
        # Check if this is our target prediction
        if target_id in str(data):
            print(f"✓ Found target ID: {target_id}")
    except json.JSONDecodeError:
        print(f"\nMessage {message_count} (raw):")
        print(message.value)
    
    # Limit output to first 20 messages
    if message_count >= 20:
        print("\n... (showing first 20 messages)")
        break

if message_count == 0:
    print("Topic is empty!")
else:
    print(f"\nTotal messages shown: {message_count}")
