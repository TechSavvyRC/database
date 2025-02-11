CREATE DATABASE ecommerce;
USE ecommerce;

CREATE TABLE ecom_transactions (
    transaction_id       VARCHAR(255)  NOT NULL PRIMARY KEY,
    order_id             VARCHAR(255)  NOT NULL,
    item_category        VARCHAR(255),
    item_subcategory     VARCHAR(255),
    item_name            VARCHAR(255),
    item_make            VARCHAR(255),
    item_model           VARCHAR(255),
    item_cost            DECIMAL(10,2),
    transaction_type     VARCHAR(50),
    transaction_status   VARCHAR(50),
    payment_mode         VARCHAR(50),
    account_id           VARCHAR(255),
    order_date           DATETIME,
    delivery_date        DATETIME,
    response_time        DECIMAL(10,2),
    customer_name        VARCHAR(255),
    customer_mobile      VARCHAR(15),
    customer_email       VARCHAR(255),
    country              VARCHAR(255),
    city                 VARCHAR(255),
    currency             VARCHAR(10),
    timestamp            DATETIME
);

