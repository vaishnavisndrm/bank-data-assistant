
PRAGMA foreign_keys = ON;

CREATE TABLE branches (
    branch_id      TEXT PRIMARY KEY,      -- e.g. BR001
    branch_name    TEXT NOT NULL,
    ifsc_code      TEXT NOT NULL UNIQUE,
    city           TEXT NOT NULL,
    state          TEXT NOT NULL,
    region         TEXT NOT NULL,         -- North/South/East/West/Central
    opened_date    DATE NOT NULL
);

CREATE TABLE customers (
    cif_id         TEXT PRIMARY KEY,      -- Customer Information File ID (one per person)
    first_name     TEXT NOT NULL,
    last_name      TEXT NOT NULL,
    gender         TEXT CHECK (gender IN ('M','F','O')),
    date_of_birth  DATE NOT NULL,
    pan_number     TEXT UNIQUE,
    mobile         TEXT,
    email          TEXT,
    occupation     TEXT,
    annual_income  REAL,
    kyc_status     TEXT CHECK (kyc_status IN ('Verified','Pending','Expired')),
    risk_category  TEXT CHECK (risk_category IN ('Low','Medium','High')),
    home_branch_id TEXT NOT NULL REFERENCES branches(branch_id),
    customer_since DATE NOT NULL
);

CREATE TABLE accounts (
    account_no     TEXT PRIMARY KEY,
    cif_id         TEXT NOT NULL REFERENCES customers(cif_id),  -- many accounts per CIF
    branch_id      TEXT NOT NULL REFERENCES branches(branch_id),
    account_type   TEXT CHECK (account_type IN ('Savings','Current','Fixed Deposit','Recurring Deposit','Salary')),
    status         TEXT CHECK (status IN ('Active','Dormant','Closed','Frozen')),
    open_date      DATE NOT NULL,
    close_date     DATE,
    balance        REAL NOT NULL,
    currency       TEXT DEFAULT 'INR',
    interest_rate  REAL
);

CREATE TABLE transactions (
    txn_id         TEXT PRIMARY KEY,
    account_no     TEXT NOT NULL REFERENCES accounts(account_no),
    txn_date       DATE NOT NULL,
    txn_time       TEXT,
    txn_type       TEXT CHECK (txn_type IN ('Credit','Debit')),
    channel        TEXT CHECK (channel IN ('UPI','NEFT','RTGS','IMPS','ATM','Cash','Cheque','Card','NetBanking')),
    amount         REAL NOT NULL,
    balance_after  REAL,
    counterparty   TEXT,
    description    TEXT,
    branch_id      TEXT REFERENCES branches(branch_id)  -- branch where txn originated
);

CREATE TABLE loans (
    loan_id        TEXT PRIMARY KEY,
    cif_id         TEXT NOT NULL REFERENCES customers(cif_id),
    branch_id      TEXT NOT NULL REFERENCES branches(branch_id),
    loan_type      TEXT CHECK (loan_type IN ('Home','Personal','Vehicle','Education','Business','Gold')),
    principal      REAL NOT NULL,
    interest_rate  REAL NOT NULL,
    tenure_months  INTEGER NOT NULL,
    disbursed_date DATE NOT NULL,
    outstanding    REAL NOT NULL,
    emi_amount     REAL NOT NULL,
    days_past_due  INTEGER DEFAULT 0,
    npa_status     TEXT CHECK (npa_status IN ('Standard','SMA','Substandard','Doubtful','Loss'))
);

CREATE INDEX idx_acc_cif ON accounts(cif_id);
CREATE INDEX idx_acc_branch ON accounts(branch_id);
CREATE INDEX idx_txn_acc ON transactions(account_no);
CREATE INDEX idx_txn_date ON transactions(txn_date);
CREATE INDEX idx_loan_cif ON loans(cif_id);
CREATE INDEX idx_cust_branch ON customers(home_branch_id);
