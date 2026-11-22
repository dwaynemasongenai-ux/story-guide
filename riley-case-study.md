# Riley: running a support bot in production for three years

Riley was the support chatbot at Relias, an online training company for healthcare professionals. I ran it from October 2020 to February 2024, first on Salesforce and then on Ada, across several branded sites, including nurse.com and distancecme.com. I owned the conversation design, the testing, the product roadmap and the release dates, and I worked directly with the release engineer to ship changes.

This is a written case study because the real material is proprietary. There are no screenshots, internal data or customer conversations here, only what I did and what I learned. For a project I can show openly, see [Story Guide](README.md).

## The people Riley served

Most of the people who reached Riley were learners, healthcare professionals with questions such as how to finish a course or print a continuing-education certificate. They wanted a quick path to an answer or to a person.

## Problem 1: users kept typing the word agent

When I read real conversation transcripts, I noticed users repeatedly typing the word agent. They were not working through the bot. They were trying to get around it.

I treated that as feedback on the design, not on the users. I redesigned the flow around that pattern. Containment rose by 30% and user satisfaction by 25%.

## Problem 2: a disagreement about tone

When a communications manager joined, they began changing Riley's tone and wording. My first reaction was to resist.

Instead of arguing about taste, we used the analytics and walked through the customer's journey together, one step at a time. That let us agree on which changes to keep and which to leave as they were. One change was structural: I shortened the main menu and built more branches from the main-menu issue types. People interacted with the bot more, and more cases were fully resolved without confusion.

## How I tested changes

Every release followed the same routine:

1. **Evaluate.** I checked how the models handled the change.
2. **Label.** I tagged conversations by issue type, such as a login issue, a billing issue or a human escalation.
3. **Test it myself.** I ran my own checks before anyone else saw it.
4. **UAT.** About two weeks, with testers asked to try to break the bot. A good test described the problem indirectly, such as being locked out of an account, so the bot had to work out what was wrong instead of matching a keyword.
5. **Release and record.** I kept a record of every change.
6. **Roll back.** Anything that did not help could be undone using that record.

I also read the error logs, not only the transcripts, to find failed API calls and broken flow steps. For monthly stakeholder updates I built Salesforce and Power BI dashboards on top support issues, case closure rates and bot performance.

## One thing I would do differently

On one release, the testers I had recruited got too busy, and I ended up as the only tester. I delayed the deployment by a couple of weeks instead of shipping it half tested. The extra testing was worth it: it caught grammar errors, broken links, and cases that were not closing automatically or were being logged with the wrong case type.

The lesson I took from it is to tell testers the deadline up front and ask them to say early if they can't make it, so a gap shows up in week one, not week two.

## Related work

On the nurse.com bot, I built course-recommendation logic using API calls and JSON responses and showed a recommendation carousel to stakeholders on a test account.
