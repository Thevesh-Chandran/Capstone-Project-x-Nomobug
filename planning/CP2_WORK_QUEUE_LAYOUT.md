# Work page layout

Customer follow-up is retained as the main work queue. A left-side view selector separates all records, reminders in the next seven days, records needing checks, and team progress. A wider table opens the existing customer review drawer. Search remains available within each view.

The booking-calendar entry sits above the queue. Customer history, payment overview and maps are reachable from the view rail. Help is collapsed by default.

Reminder dates are not payment due dates or proof of payment. Progress is a staff record, separate from source balances. No messages are sent automatically. The removed Ollama assistant remains disabled.

Validation: 47 Python checks passed; booking-calendar DOM interactions passed; work-queue DOM interactions passed (views, search, review and navigation). JavaScript syntax passed. A visual inspection of the deployed browser remains outstanding.

Build: 01ee8d5f-26f1-4b22-b038-41047952c6ae. Previous revision: cp2-portal-00061-4d9.

Deployed revision: cp2-portal-00062-cpw; 100% traffic and planning tag updated.

## Compact CRM revision

Removed the promotional banner and nested left navigation from Work. The page now has one title/action row, a visible source-freshness notice, horizontal follow-up views, search/navigation toolbar and a full-width record list. Reminder, missing-information and progress counts have distinct restrained colours. Customer initials aid row scanning. Help and payment-status explanations are available in expandable help and the existing review drawer.

Customer follow-up, search, review actions, booking navigation and manual progress persistence are retained. No financial facts, model outputs or authentication rules changed. No prediction or automatic messaging is added by this layout.

Validation: 47 Python tests and both workspace/calendar interaction checks passed. Browser visual inspection has not been completed; do not describe this as a visually approved replica of Zoho.
Build: 9b92d9fc-d92e-4230-90c4-985c54c21597.

## Live browser verification

Inspected the deployed planning URL in Chrome at 1440 x 810 desktop size. Work shows the horizontal view tabs and full record columns without overlap. Reminder tab changed the displayed list from 13 records to 3. Review opened the customer drawer with source balances, message draft and progress fields, and Close returned to the queue. Plan navigation loaded the team calendar and existing blocked/appointment events. The floating Guide is absent. No progress records, Calendar events or messages were changed during this inspection.

Scope: desktop Work/reminder/review and Plan/calendar rendering. This does not certify every website page or the financial refresh. The page still displays the genuine 28 October financial-source warning; the separately loaded Calendar feed displayed 1 November 06:01 MYT.
