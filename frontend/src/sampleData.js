export const sampleTransactions = [
  {
    id: "tx1001",
    customer_id: "CUST-001",
    account_id: "ACC-123",
    merchant_id: "M-SUSPICIOUS-SHOP",
    device_id: "DEV-01",
    ip_address: "10.0.0.5",
    amount: 2400,
    currency: "USD",
    timestamp: new Date().toISOString(),
    channel: "WEB",
    country: "US"
  },
  {
    id: "tx1002",
    customer_id: "CUST-001",
    account_id: "ACC-123",
    merchant_id: "M-SUSPICIOUS-SHOP",
    device_id: "DEV-01",
    ip_address: "10.0.0.5",
    amount: 2600,
    currency: "USD",
    timestamp: new Date(Date.now() + 3 * 60 * 1000).toISOString(),
    channel: "WEB",
    country: "US"
  },
  {
    id: "tx1003",
    customer_id: "CUST-001",
    account_id: "ACC-123",
    merchant_id: "M-COFFEE",
    device_id: "DEV-02",
    ip_address: "47.33.21.9",
    amount: 4.75,
    currency: "USD",
    timestamp: new Date(Date.now() - 60 * 60 * 1000).toISOString(),
    channel: "POS",
    country: "US"
  },
  {
    id: "tx1004",
    customer_id: "CUST-002",
    account_id: "ACC-555",
    merchant_id: "M-GROCERY",
    device_id: "DEV-09",
    ip_address: "101.88.33.19",
    amount: 80,
    currency: "USD",
    timestamp: new Date().toISOString(),
    channel: "POS",
    country: "US"
  }
];
