# 🎓 berkant.app - Student CV & Portfolio Catalog

[![Deploy Status](https://img.shields.io/badge/build-passing-brightgreen)](#)
[![License: CC BY--NC 4.0](https://img.shields.io/badge/License-CC%20BY--NC%204.0-lightgrey.svg)](https://creativecommons.org/licenses/by-nc/4.0/)
[![Hosting: Firebase](https://img.shields.io/badge/Hosting-Firebase-FFCA28?logo=firebase&logoColor=black)](#)

**Live Domain:** [berkant.app](https://berkant.app) *(Active upon production deployment)*
**Project Timeline:** March 01, 2026 – March 30, 2026

## 📖 Project Overview
`berkant.app` is a highly optimized, responsive static web platform designed to showcase software development student resumes, technical roles, and interactive runnable projects (including Godot WASM games). 

To ensure 100% uptime, zero infrastructure costs, and strict adherence to the one-month project deadline, the architecture utilizes a serverless static approach. Student submissions are collected via Google Workspace and manually integrated into the codebase. This mitigates the risk of dynamic database failures while demonstrating a clean, maintainable, and secure front-end architecture.

## 👥 Team & Roles (2-Person Agile Team)
This project is developed and maintained by a cross-functional Full Stack/DevOps team:

* **Berkant (Lead DevOps & Full Stack):** Manages cloud infrastructure (Firebase Hosting), DNS routing via Cloudflare, GitHub repository version control, CI/CD pipelines, and core static site architecture.
* **[Classmate's Name] (Project Manager & UI/Content Lead):** Manages Jira task tracking, develops the frontend UI and vanilla JavaScript filtering logic, and handles the manual integration and formatting of student assets.

## 🛠️ Technology & DevOps Stack
* **Frontend:** HTML5, CSS3 (Tailwind via CDN), Vanilla JavaScript.
* **Hosting:** Firebase Hosting (Spark Free Tier).
* **DNS & Security:** Cloudflare (pointing to Firebase via custom domain).
* **CI/CD (Shift-Left):** GitHub Actions integrated with Google Gemini AI for automated Pull Request code reviews and linting before merging to the `main` branch.
* **Asset Management:** Google Drive / Google Forms for ingesting heavy media files and student submissions.

## ✨ Key Technical Features
* **Zero-Cost Architecture:** Fully utilizes free-tier enterprise tools while maintaining a custom top-level domain (`.app`).
* **Client-Side Filtering:** Instantaneous category filtering (Artists, Coders, Designers) using HTML `data-attributes` and vanilla JavaScript, requiring zero database queries or server-side rendering.
* **Optimized WASM Hosting:** Godot game projects are lazy-loaded via interactive thumbnails to drastically reduce initial page load times and preserve Firebase bandwidth limits.
* **Fully Responsive:** Accessible and optimized for Mobile, Tablet, and Desktop environments.

## 🚀 Local Development Setup
Since this relies on a static architecture without a complex local backend, onboarding is instantaneous:

1.  **Clone the repository:**
    ```bash
    git clone [https://github.com/YOUR_USERNAME/berkant.app.git](https://github.com/YOUR_USERNAME/berkant.app.git)
    ```
2.  **Navigate to the project directory:**
    ```bash
    cd berkant.app
    ```
3.  **Run the project:**
    Open the folder in VS Code and use the **Live Server** extension for hot-reloading, or simply open `index.html` in any modern web browser.

## 📄 Licensing & Permissions
This entire repository and its contents are protected under the **Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0) License**.

* You are free to view and learn from the source code for educational purposes.
* You **may not** use this codebase, the website design, or any hosted student content (CVs, images, games) for commercial purposes. 
* Direct permission is required from the original authors to reuse any personal student data or project assets hosted on this platform.

## 🗺️ Project Management & Architecture 
*(Administrative notes for grading)*
* **Task Tracking:** Managed via Jira (Kanban methodology).
* **Documentation:** The complete Excel project plan (Budget, Risk Management, Timeline) and the UML Deployment Diagram are located in the repository files or on the associated project management board.
