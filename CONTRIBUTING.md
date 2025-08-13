# Welcome to Home Assistant Trafiklab Integration contributing guide <!-- omit in toc -->

Thank you for investing your time in contributing to my project! :sparkles:

In this guide you will get an overview of the contribution workflow from opening an issue, creating a PR, reviewing, and merging the PR.

## New contributor guide

To get an overview of the project, read the [README](../README.md) file. Here are some resources to help you get started with open source contributions, should you be new in the area:

- [Finding ways to contribute to open source on GitHub](https://docs.github.com/en/get-started/exploring-projects-on-github/finding-ways-to-contribute-to-open-source-on-github)
- [Set up Git](https://docs.github.com/en/get-started/git-basics/set-up-git)
- [GitHub flow](https://docs.github.com/en/get-started/using-github/github-flow)
- [Collaborating with pull requests](https://docs.github.com/en/github/collaborating-with-pull-requests)


## Getting started

I assume you've already took a look at the code for the integration as well as gone through the [README](../README.md) so that you already know what the integration does and how it is built up. If not, please take some time to familiarize. 

### Issues

#### Create a new issue

If you spot a problem with the integration, or wish to enhance functionality [check if an issue already exists](https://github.com/MrSjodin/HomeAssistant_Trafiklab_Integration/issues). If a related issue doesn't exist, you can open a new issue using a relevant [issue form](https://github.com/MrSjodin/HomeAssistant_Trafiklab_Integration/issues/new/choose).

#### Solve an issue

Scan through our [existing issues](https://github.com/MrSjodin/HomeAssistant_Trafiklab_Integration/issues) to find one that you want to contribute on. If you find an issue to work on, you are welcome to open a PR with a fix.

### Make Changes

#### Make changes locally

1. Fork the repository.
- Using GitHub Desktop:
  - [Getting started with GitHub Desktop](https://docs.github.com/en/desktop/installing-and-configuring-github-desktop/getting-started-with-github-desktop) will guide you through setting up Desktop.
  - Once Desktop is set up, you can use it to [fork the repo](https://docs.github.com/en/desktop/contributing-and-collaborating-using-github-desktop/cloning-and-forking-repositories-from-github-desktop)!

- Using the command line:
  - [Fork the repo](https://docs.github.com/en/github/getting-started-with-github/fork-a-repo#fork-an-example-repository) so that you can make your changes without affecting the original project until you're ready to merge them.

2. Create a working branch and start with your changes!

### Test your changes

Needless to say, but please make sure to test the changes prior to commit.
- Make sure that the integration loads
- Make sure that the integration doesn't rise any errors in the logs
- Make sure that the integration and sensors appear as you expect

### Commit your update

Commit the changes once you are happy with them.

### Pull Request

When you're finished with the changes, create a pull request, also known as a PR.
- Fill the "Ready for review" template so that we can review your PR. This template helps reviewers understand your changes as well as the purpose of your pull request.
- Don't forget to [link PR to issue](https://docs.github.com/en/issues/tracking-your-work-with-issues/linking-a-pull-request-to-an-issue) if you are solving one.
- Enable the checkbox to [allow maintainer edits](https://docs.github.com/en/github/collaborating-with-issues-and-pull-requests/allowing-changes-to-a-pull-request-branch-created-from-a-fork) so the branch can be updated for a merge.
Once you submit your PR, your proposal will be revised. We may ask questions or request additional information.
- We may ask for changes to be made before a PR can be merged, either using [suggested changes](https://docs.github.com/en/github/collaborating-with-issues-and-pull-requests/incorporating-feedback-in-your-pull-request) or pull request comments. You can apply suggested changes directly through the UI. You can make any other changes in your fork, then commit them to your branch.
- As you update your PR and apply changes, mark each conversation as [resolved](https://docs.github.com/en/github/collaborating-with-issues-and-pull-requests/commenting-on-a-pull-request#resolving-conversations).
- If you run into any merge issues, checkout this [git tutorial](https://github.com/skills/resolve-merge-conflicts) to help you resolve merge conflicts and other issues.

### Your PR is merged!

Congratulations :tada::tada: Many thanks for your contribution! :sparkles:.

Once your PR is merged, your contributions will be included in the next release. If your contribution is planned for an upcoming release it should show up in the upcoming [milestone](https://github.com/MrSjodin/HomeAssistant_Trafiklab_Integration/milestones).
