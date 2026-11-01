# Telegram Notify

A tool that watches web pages for changes in the products they list and tells its owner about them through Telegram. It started with the Marukyu-Koyamaen matcha shop and is meant to grow to other pages.

## Language

**Watch** (監控項目):
One web page being monitored, together with the knowledge of how to read the Products on it.
_Avoid_: Monitor, target, job, task

**Product** (商品):
An item listed on a Watch's page, identified by the ID the shop gives it.
_Avoid_: Item, listing

**Baseline** (基準線):
The first recording of a Watch's Products, kept so later runs have something to compare against. Recording a Baseline produces no Event.
_Avoid_: Snapshot, initial state

**Event** (事件):
A change detected on a Product since the last check. Every Event is one of the two kinds below.
_Avoid_: Alert, update, change

**New Product** (新品上架):
An Event: a Product appears on a Watch's page that was not there before.

**Restock** (補貨):
An Event: a Product that was out of stock becomes in stock.
_Avoid_: Back in stock

**Notification** (通知):
The Telegram message that tells the owner about one Event.
_Avoid_: Message, alert
