# Digital Deregulated Labs – Operational Intelligence Dashboards

This repository contains a working dashboard built as part of Digital Deregulated Labs portfolio.

The goal of these projects is to demonstrate how complex operational data can be translated into clear,
decision-friendly dashboards for both technical users and non-experts.

These dashboards include short "Insights" sections that explain what the data means and why it matters.

Note: These insights are examples of how an analyst might interpret the data. They are included for educational
and demonstration purposes and should not be considered formal operational guidance.

# ISO Electricity Pricing Dashboard

Live App:
https://digitalderegulated-labs-energy-pricing-dashboard.streamlit.app

## Overview

This dashboard visualizes electricity price data from U.S. ISO markets and explains price behavior
in a way that is understandable to both traders and non-technical stakeholders.

Electricity markets produce large volumes of real-time price data. Without context,
these signals are difficult to interpret.

This dashboard focuses on three core questions:

• Are prices rising or falling?
• How volatile is the market?
• Where are potential risk signals emerging?

## Key Features

Day-Ahead vs Real-Time price monitoring

Price volatility indicators

Spike detection and percentile analysis

Intraday heatmaps

Trader and executive views

## Example Insights

Insights are displayed below each visualization to explain what the chart means.

Example:

Signal  
Price spikes exceeded the 95th percentile threshold during the afternoon trading window.

Implication  
This suggests elevated system stress or congestion during peak demand hours.

Next Step  
Traders may monitor hub-to-load spreads or congestion patterns.

## Data Sources

CAISO OASIS  
Public ISO market data

## Purpose

This project demonstrates how complex energy market data can be transformed into clear,
actionable dashboards that support both operational and executive decision making.
