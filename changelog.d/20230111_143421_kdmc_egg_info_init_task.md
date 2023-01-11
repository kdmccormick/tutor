<!--
Create a changelog entry for every new user-facing change. Please respect the following instructions:
- Indicate breaking changes by prepending an explosion 💥 character.
- Prefix your changes with either [Bugfix], [Improvement], [Feature], [Security], [Deprecation].
- You may optionally append "(by @<author>)" at the end of the line, where "<author>" is either one (just one)
  of your GitHub username, real name or affiliated organization. These affiliations will be displayed in
  the release notes for every release.
-->

- [Improvement] Before, Open edX developers needed to pip-install requirements when bind-mounting a local copy of edx-platform the first time. Now, they can just launch the bind-mounted platform instead: ``tutor ... launch --mount=edx-platform`` (by @kdmccormick).
