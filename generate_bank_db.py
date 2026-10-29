import sqlite3, random, csv, os
from datetime import date, timedelta

random.seed(42)
OUT = "/tmp/outputs"
os.makedirs(OUT, exist_ok=True)
DB = f"{OUT}/central_bank_sample.db"
if os.path.exists(DB):
    os.remove(DB)

SCHEMA = """
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
"""

with open(f"{OUT}/schema.sql", "w") as f:
    f.write(SCHEMA)

TODAY = date(2026, 10, 20)
def rdate(a, b):
    return a + timedelta(days=random.randint(0, (b - a).days))

# ---------- Branches ----------
branch_src = [
    ("Chennai T Nagar", "Chennai", "Tamil Nadu", "South"),
    ("Chennai Anna Nagar", "Chennai", "Tamil Nadu", "South"),
    ("Coimbatore RS Puram", "Coimbatore", "Tamil Nadu", "South"),
    ("Bengaluru MG Road", "Bengaluru", "Karnataka", "South"),
    ("Hyderabad Banjara Hills", "Hyderabad", "Telangana", "South"),
    ("Mumbai Fort", "Mumbai", "Maharashtra", "West"),
    ("Pune Camp", "Pune", "Maharashtra", "West"),
    ("Ahmedabad CG Road", "Ahmedabad", "Gujarat", "West"),
    ("New Delhi Connaught Place", "New Delhi", "Delhi", "North"),
    ("Chandigarh Sector 17", "Chandigarh", "Chandigarh", "North"),
    ("Lucknow Hazratganj", "Lucknow", "Uttar Pradesh", "North"),
    ("Kolkata Park Street", "Kolkata", "West Bengal", "East"),
    ("Bhubaneswar Janpath", "Bhubaneswar", "Odisha", "East"),
    ("Bhopal MP Nagar", "Bhopal", "Madhya Pradesh", "Central"),
]
branches = []
for i, (n, c, s, r) in enumerate(branch_src, 1):
    bid = f"BR{i:03d}"
    branches.append((bid, n, f"CBIN0{i:06d}", c, s, r, rdate(date(1985,1,1), date(2015,12,31)).isoformat()))

# ---------- Customers ----------
male = ["Arun","Karthik","Rahul","Vikram","Suresh","Anil","Rajesh","Manoj","Sanjay","Deepak","Prakash","Ganesh","Naveen","Mohan","Ramesh"]
female = ["Priya","Lakshmi","Anita","Sunita","Kavitha","Meena","Divya","Pooja","Neha","Revathi","Sangeetha","Radha","Shalini","Anjali","Deepa"]
last = ["Kumar","Sharma","Iyer","Reddy","Nair","Patel","Singh","Gupta","Rao","Das","Menon","Pillai","Banerjee","Joshi","Verma","Chatterjee","Naidu","Mehta"]
occ = [("Salaried",0.45),("Self-Employed",0.2),("Business Owner",0.12),("Professional",0.1),("Retired",0.07),("Student",0.03),("Farmer",0.03)]
occ_inc = {"Salaried":(3,18),"Self-Employed":(4,25),"Business Owner":(8,80),"Professional":(10,50),"Retired":(2,10),"Student":(0.5,3),"Farmer":(1.5,8)}

def pick_occ():
    r, a = random.random(), 0
    for o, w in occ:
        a += w
        if r <= a:
            return o
    return "Salaried"

N_CUST = 2000
customers = []
for i in range(1, N_CUST + 1):
    cif = f"CIF{100000 + i}"
    g = random.choices(["M","F","O"], [0.52, 0.47, 0.01])[0]
    fn = random.choice(female if g == "F" else male)
    ln = random.choice(last)
    dob = rdate(date(1950,1,1), date(2004,12,31))
    o = pick_occ()
    if o == "Student" and (TODAY - dob).days > 28*365: o = "Salaried"
    if o == "Retired" and (TODAY - dob).days < 55*365: o = "Self-Employed"
    lo, hi = occ_inc[o]
    income = round(random.uniform(lo, hi) * 100000, 0)
    hb = random.choice(branches)[0]
    since = rdate(max(date(2005,1,1), dob + timedelta(days=18*365)), date(2025,12,31))
    pan = "".join(random.choices("ABCDEFGHJKLMNPQRSTUVWXYZ", k=5)) + f"{random.randint(1000,9999)}" + random.choice("ABCDEFGHJKLMNPQRSTUVWXYZ")
    kyc = random.choices(["Verified","Pending","Expired"], [0.88, 0.07, 0.05])[0]
    risk = random.choices(["Low","Medium","High"], [0.7, 0.22, 0.08])[0]
    customers.append((cif, fn, ln, g, dob.isoformat(), pan, f"9{random.randint(100000000,999999999)}",
                      f"{fn.lower()}.{ln.lower()}{random.randint(1,999)}@example.com", o, income, kyc, risk, hb, since.isoformat()))

# ---------- Accounts (1 to 5 per CIF) ----------
accounts, acc_counter = [], 5000000000
cust_map = {c[0]: c for c in customers}
for c in customers:
    n = random.choices([1,2,3,4,5], [0.35,0.3,0.2,0.1,0.05])[0]
    types = []
    base = "Salary" if c[8] == "Salaried" and random.random() < 0.7 else ("Current" if c[8] in ("Business Owner","Self-Employed") and random.random()<0.7 else "Savings")
    types.append(base)
    while len(types) < n:
        types.append(random.choices(["Savings","Current","Fixed Deposit","Recurring Deposit"], [0.35,0.1,0.35,0.2])[0])
    since = date.fromisoformat(c[13])
    for t in types:
        acc_counter += random.randint(1, 37)
        # ~75% of accounts at home branch, rest at other branches (multi-branch customers)
        br = c[12] if random.random() < 0.75 else random.choice(branches)[0]
        od = rdate(since, TODAY - timedelta(days=30))
        status = random.choices(["Active","Dormant","Closed","Frozen"], [0.85,0.08,0.05,0.02])[0]
        cd = rdate(od + timedelta(days=30), TODAY).isoformat() if status == "Closed" and od + timedelta(days=30) < TODAY else None
        if status == "Closed" and cd is None: status = "Active"
        inc = c[9] or 100000
        if t in ("Savings","Salary"): bal, rate = random.uniform(0.2, 6) * inc / 12, 3.0
        elif t == "Current": bal, rate = random.uniform(0.5, 10) * inc / 12, 0.0
        elif t == "Fixed Deposit": bal, rate = random.uniform(0.3, 3) * inc, random.choice([6.5,6.75,7.0,7.25])
        else: bal, rate = random.uniform(0.1, 1) * inc, random.choice([6.0,6.5,6.75])
        if status == "Closed": bal = 0
        accounts.append((f"{acc_counter}", c[0], br, t, status, od.isoformat(), cd, round(bal, 2), "INR", rate))

# ---------- Transactions ----------
channels = ["UPI","NEFT","RTGS","IMPS","ATM","Cash","Cheque","Card","NetBanking"]
merchants = ["Amazon","Flipkart","Swiggy","Zomato","BigBasket","IRCTC","Reliance Retail","Airtel","BESCOM","TNEB","Apollo Pharmacy","Uber","PhonePe Transfer","Landlord","Insurance Premium","Mutual Fund SIP","Petrol Pump"]
txns, tn = [], 0
for a in accounts:
    acc_no, cif, br, t, status, od, cd, bal, _, _ = a
    if t in ("Fixed Deposit",):
        n = random.randint(1, 3)
    elif t == "Recurring Deposit":
        n = random.randint(6, 14)
    elif status in ("Dormant","Frozen"):
        n = random.randint(0, 4)
    else:
        n = random.randint(15, 40)
    start = date.fromisoformat(od)
    end = date.fromisoformat(cd) if cd else TODAY
    start = max(start, TODAY - timedelta(days=540))
    if start >= end: continue
    inc = (cust_map[cif][9] or 100000) / 12
    running = bal
    rows = []
    for _ in range(n):
        d = rdate(start, end)
        if t == "Fixed Deposit":
            tt, ch, amt, cp, desc = "Credit", "NetBanking", round(random.uniform(0.5,2)*inc*3, 2), "FD Booking", "FD deposit"
        elif t == "Recurring Deposit":
            tt, ch, amt, cp, desc = "Credit", "NetBanking", round(random.choice([2000,5000,10000,15000]), 2), "RD Installment", "Monthly RD"
        else:
            tt = random.choices(["Credit","Debit"], [0.35,0.65])[0]
            if tt == "Credit":
                ch = random.choices(["NEFT","UPI","IMPS","Cash","Cheque","RTGS"], [0.3,0.25,0.1,0.15,0.1,0.1])[0]
                if t == "Salary" and random.random() < 0.5:
                    amt, cp, desc = round(inc * random.uniform(0.7, 0.9), 2), "Employer Payroll", "Salary credit"
                else:
                    amt, cp, desc = round(random.uniform(500, inc * 1.5), 2), random.choice(["Self Transfer","Client Payment","Friend/Family","Interest Credit"]), "Inward transfer"
            else:
                ch = random.choices(["UPI","Card","ATM","NEFT","IMPS","NetBanking","Cheque","RTGS"], [0.35,0.2,0.12,0.08,0.07,0.08,0.05,0.05])[0]
                amt = round(random.lognormvariate(7.5, 1.1), 2)
                if ch == "ATM": amt = float(random.choice([500,1000,2000,5000,10000]))
                if random.random() < 0.01: amt = round(random.uniform(1_000_000, 5_000_000), 2)  # rare large txn (AML analysis)
                cp, desc = random.choice(merchants), "Purchase/Payment"
        txn_br = br if ch in ("Cash","Cheque") or random.random() < 0.8 else random.choice(branches)[0]
        rows.append([d, tt, ch, amt, cp, desc, txn_br])
    rows.sort(key=lambda r: r[0])
    for r in rows:
        tn += 1
        run_amt = r[3] if r[1] == "Credit" else -r[3]
        running += run_amt
        txns.append((f"TXN{tn:08d}", acc_no, r[0].isoformat(), f"{random.randint(8,21):02d}:{random.randint(0,59):02d}:{random.randint(0,59):02d}",
                     r[1], r[2], r[3], round(max(running, 0), 2), r[4], r[5], r[6]))

# ---------- Loans ----------
loans, ln_ = [], 0
ltypes = {"Home": (1_500_000, 8_000_000, 8.5, 180, 240), "Personal": (100_000, 1_000_000, 12.5, 24, 60),
          "Vehicle": (300_000, 1_500_000, 9.5, 36, 84), "Education": (200_000, 2_000_000, 9.0, 60, 120),
          "Business": (500_000, 5_000_000, 11.0, 24, 84), "Gold": (50_000, 500_000, 9.0, 6, 24)}
for c in customers:
    if random.random() > 0.3: continue
    for _ in range(random.choices([1,2],[0.85,0.15])[0]):
        lt = random.choice(list(ltypes))
        lo, hi, rate, tmin, tmax = ltypes[lt]
        prin = round(random.uniform(lo, hi), -3)
        ten = random.randrange(tmin, tmax + 1, 12)  # tenure in months, always >= tmin
        disb = rdate(date(2018,1,1), date(2026,6,30))
        r = rate / 1200
        emi = prin * r * (1 + r) ** ten / ((1 + r) ** ten - 1)
        elapsed = min((TODAY.year - disb.year) * 12 + TODAY.month - disb.month, ten)
        out = prin * ((1 + r) ** ten - (1 + r) ** elapsed) / ((1 + r) ** ten - 1) if elapsed < ten else 0
        dpd = random.choices([0, random.randint(1,29), random.randint(30,89), random.randint(90,180), random.randint(181,400)], [0.85,0.06,0.04,0.03,0.02])[0] if out > 0 else 0
        npa = "Standard" if dpd == 0 else "SMA" if dpd < 90 else "Substandard" if dpd < 365 else "Doubtful"
        if dpd >= 300 and random.random() < 0.3: npa = "Loss"
        ln_ += 1
        loans.append((f"LN{ln_:06d}", c[0], c[12], lt, prin, round(rate + random.uniform(-0.5, 1.5), 2), ten, disb.isoformat(), round(out, 2), round(emi, 2), dpd, npa))

# ---------- Write DB + CSV ----------
con = sqlite3.connect(DB)
con.executescript(SCHEMA)
def ins(tbl, rows):
    if rows:
        con.executemany(f"INSERT INTO {tbl} VALUES ({','.join('?'*len(rows[0]))})", rows)
ins("branches", branches); ins("customers", customers); ins("accounts", accounts)
ins("transactions", txns); ins("loans", loans)
con.commit()

for tbl in ["branches","customers","accounts","transactions","loans"]:
    cur = con.execute(f"SELECT * FROM {tbl}")
    cols = [d[0] for d in cur.description]
    os.makedirs(f"{OUT}/csv", exist_ok=True)
    with open(f"{OUT}/csv/{tbl}.csv", "w", newline="") as f:
        w = csv.writer(f); w.writerow(cols); w.writerows(cur)
    print(tbl, con.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0])
con.close()
