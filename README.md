# env-sync-gate 🔑🚪

[![GitHub Action](https://img.shields.io/badge/GitHub%20Action-v1.0.0-orange?logo=githubactions)](https://github.com/OrderStream/env-sync-gate)

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![CI](https://img.shields.io/badge/CI-Passing-brightgreen.svg)]()
[![OrderStream Polar](https://img.shields.io/badge/Polar-OrderStream-blue.svg)](https://polar.sh/orderstream)
[![Stellar XLM/USDC](https://img.shields.io/badge/Stellar-USDC%2FXLM-black.svg)](#direct-web3-wallet-monetization)
[![Base USDC](https://img.shields.io/badge/Base-USDC-0052FF.svg)](#direct-web3-wallet-monetization)

Static scanner for `process.env` and `os.environ` that prevents missing environment variable crashes in production deployments.

---

## 💥 The Friction & Dollar Cost
The most embarrassing production outages are caused by a missing 1-line environment variable:
- A developer adds `os.environ["STRIPE_WEBHOOK_SECRET"]` or `process.env.DATABASE_URL`.
- The PR is merged, but nobody updated `.env.example`, Docker Compose, or Terraform / Helm.
- Production deployment spins up and instantly crashes with `KeyError: 'STRIPE_WEBHOOK_SECRET'`, triggering an outage, rolling back releases, and waking on-call engineers.

**env-sync-gate** statically parses your entire codebase across Python, TypeScript, Node.js, and shell scripts:
1. Catches un-defaulted required environment variables missing from `.env.example`.
2. Flags dead config variables that clutter documentation.
3. Automatically generates an up-to-date `.env.example` file.

---

## 🚀 Quick Start

### Installation
```bash
pip install env-sync-gate
```

### CLI Usage
```bash
# Scan repository against .env.example
env-sync-gate scan --path .

# Auto-generate a clean .env.example from all discovered code usages
env-sync-gate generate-template --path . --out .env.example

# Check license & zero-fee wallet payment details
env-sync-gate license
```

---

## 🤖 GitHub Action Integration

```yaml
- name: Env Sync Gate CI
  uses: OrderStream/env-sync-gate@v1
  with:
    path: "."
    template: ".env.example"
    fail_on_missing: true
```

---

## 💰 Direct Web3 Wallet Monetization & Polar Integration

Support this project or purchase enterprise HashiCorp Vault / AWS Secrets Manager sync with **0 platform fees**:

- **Polar Subscription & Sponsorship:** [https://polar.sh/orderstream](https://polar.sh/orderstream)
- **Stellar Network (Native XLM / USDC):**
  - Public Key: `GABFQIK63R2NETJM7T673EAMZN4RJLLGP3OFUEJU5ZVTGWUKULZJNL6`
  - Memo (Required): `400566831`
- **EVM (Base / Arbitrum / Ethereum USDT & USDC):**
  - Address: `0x5de2b62434754bfd39ef350a3a867ed3eced5074`
