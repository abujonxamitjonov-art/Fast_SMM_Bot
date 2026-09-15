TEXT = {
"uz": {
"choose_lang":"🌐 Tilni tanlang:","share_phone":"📱 Botdan foydalanish uchun Telegram akkauntingizga ulangan telefon raqamingizni yuboring:",
"wrong_contact":"❌ Faqat shu Telegram akkauntingizga ulangan raqamni yuborishingiz mumkin.","registered":"✅ Ro‘yxatdan o‘tish yakunlandi!",
"subscribe":"📢 Botdan foydalanish uchun quyidagi kanallarga obuna bo‘ling:","check_sub":"✅ Obunani tekshirish","menu":"🏠 Asosiy menyu",
"topup":"💳 Balansni to‘ldirish","back":"⬅️ Orqaga","no_balance":"❌ Balansingiz yetarli emas.\nNarx: {price:,} so‘m\nBalansingiz: {balance:,} so‘m\nYetishmayapti: {short:,} so‘m",
"payment_amount":"💵 To‘ldirmoqchi bo‘lgan summangizni kiriting.\nMinimal summa: {minimum:,} so‘m.","bad_amount":"❌ Summani faqat musbat son ko‘rinishida yuboring.",
"send_receipt":"🧾 {amount:,} so‘m to‘lov uchun chekni shu yerga yuboring.","payment_sent":"✅ Chekingiz adminga yuborildi. Tasdiqlanishini kuting.",
"payment_ok":"🎉 To‘lovingiz tasdiqlandi!\n💰 Hisobingizga {amount:,} so‘m qo‘shildi.\n🎁 Bonus: {bonus:,} so‘m\n💳 Joriy balans: {balance:,} so‘m",
"payment_no":"❌ To‘lovingiz rad etildi.","ref_info":"👥 Sizning referral havolangiz:\n{link}\n\nHar bir to‘liq ro‘yxatdan o‘tgan taklif uchun: 200 so‘m.",
"order_created":"✅ Buyurtma qabul qilindi.\n🆔 Buyurtma: #{order}\n💰 Narx: {price:,} so‘m"},
"ru": {
"choose_lang":"🌐 Выберите язык:","share_phone":"📱 Отправьте номер, привязанный к вашему Telegram аккаунту:",
"wrong_contact":"❌ Можно отправить только номер этого Telegram аккаунта.","registered":"✅ Регистрация завершена!",
"subscribe":"📢 Подпишитесь на следующие каналы:","check_sub":"✅ Проверить подписку","menu":"🏠 Главное меню",
"topup":"💳 Пополнить баланс","back":"⬅️ Назад","no_balance":"❌ Недостаточно средств.\nЦена: {price:,} сум\nБаланс: {balance:,} сум\nНе хватает: {short:,} сум",
"payment_amount":"💵 Введите сумму пополнения.\nМинимум: {minimum:,} сум.","bad_amount":"❌ Введите положительную сумму.",
"send_receipt":"🧾 Отправьте чек оплаты на сумму {amount:,} сум.","payment_sent":"✅ Чек отправлен администратору.",
"payment_ok":"🎉 Платёж подтверждён!\n💰 Зачислено: {amount:,} сум\n🎁 Бонус: {bonus:,} сум\n💳 Баланс: {balance:,} сум",
"payment_no":"❌ Платёж отклонён.","ref_info":"👥 Ваша реферальная ссылка:\n{link}\n\nЗа каждого полностью зарегистрированного приглашённого: 200 сум.",
"order_created":"✅ Заказ принят.\n🆔 Заказ: #{order}\n💰 Цена: {price:,} сум"}}

def t(lang, key, **kw):
    return TEXT.get(lang, TEXT["uz"]).get(key, key).format(**kw)
