# FAST SMM BOT

Render-ready Telegram SMM bot.

## Included
- Uzbek/Russian onboarding.
- Telegram contact-only registration; contact must belong to the pressing account.
- Mandatory channels/groups with optional expiration and admin notification.
- Common customer balance.
- Manual card top-up with receipt review and two-step admin confirmation.
- Idempotent payment crediting and ledger history.
- 50 UZS bonus per complete 50,000 UZS confirmed top-up.
- 200 UZS referral reward only after full registration and mandatory subscriptions.
- Locksmm SMM service catalog, markup, order creation and status synchronization.
- Telegram Premium, Stars and Gifts catalogs with manual admin fulfillment.
- Proof channel posts with one `📊 Holatni ko‘rish` button.
- Admin-only command menu.
- Daily broadcast loop excluding admins.
- PostgreSQL on Render.

## Render environment variables
Set these in Render, not GitHub:
- `BOT_TOKEN`
- `DATABASE_URL`
- `LOCKSMM_API_KEY`
- `HUMO_CARD`
- `VISA_CARD`
- `MASTERCARD_CARD`
- `WEBHOOK_SECRET` (recommended random secret)

The included `render.yaml` preconfigures the non-secret values and `@FastSmm_buyurtmalar` proof channel.

## Important
1. The bot must be an administrator in `@FastSmm_buyurtmalar`.
2. For mandatory channels/groups, make the bot an administrator so it can check membership.
3. Rotate any API key that has previously been exposed and put the replacement only in Render Environment Variables.
4. Render free services can sleep; an in-process 24-hour loop can therefore be delayed while the service sleeps.
