<div dir="rtl">

# ניתוח הסנסיטיביות והפרטיות עבור use case של CQA

המסמך בודק את הוכחות הסנסיטיביות והפרטיות ב-`Private_Query_Refinement.pdf` (Prop 4.2, Prop 4.5, Algorithms 1–2), ושואל אם הן תקפות כשמחליפים את ה-refinement ב-Consistent Query Answering (CQA). בסוף יש הצעה לכיוון ומיקום בספרות.

את הדוגמאות הנגדיות אפשר להריץ: `python3 scripts/sensitivity_counterexamples.py`.

> הנוסחאות במצגת (שקפים 8–30) הן תמונות ולא נבדקו. הניתוח מתבסס על ה-PDF בלבד.

---

## 1. סיכום

ההוכחות **לא תקפות** כמו שהן ל-CQA. הן מניחות ש-$Q'$ היא שאילתת selection שמחליטה על כל tuple בנפרד. ב-CQA ההחלטה אם tuple הוא certain answer תלויה ב-tuples אחרים, ולכן tuple אחד שנוסף יכול לשנות הרבה buckets. גם בתרחיש ה-refinement המקורי יש בהוכחות כמה פערים (סעיף 3).

---

## 2. הבעיה ב-CQA: Prop 4.2 (HD)

ההוכחה של $\Delta_{HD} \le 1$ מניחה ב-Case 1 שהוספת tuple $t$ משנה רק את ה-bucket של $t$. ב-CQA זה לא נכון, כי ה-FO-rewriting של $Q'$ מכיל `NOT EXISTS` על tuples שמתנגשים.

### דוגמה 1: FD מסוג Dept → City

| Name | Dept | City | Gender |
|---|---|---|---|
| e1 | R&D | Haifa | F |
| e2 | R&D | Haifa | F |
| e3 | R&D | Haifa | M |
| e4 | R&D | Haifa | M |

- $D$ עקבי, ולכן $Q(D)=Q'(D)$ ו-$HD(D)=0$.
- $D' = D \cup \{(t,\ R\&D,\ TLV,\ F)\}$. יש שני repairs, $\{e1..e4\}$ ו-$\{t\}$, ולכן $Q'(D')=\emptyset$.

| bucket | $H_Q$ | $H_{Q'}$ | $H_{p(D)}$ | איבר |
|---|---|---|---|---|
| F | 3 | 0 | 3 | 1 |
| M | 2 | 0 | 2 | 1 |

$HD(D')=2$. **השינוי הוא 2, והמאמר טוען לחסם של 1.** ‏$t$ גרם ל-e3 ו-e4 לצאת מ-$Q'$, למרות ששניהם ב-bucket אחר.

### דוגמה 2: אותו דבר עם 10 buckets
1000 עובדים ו-10 ערכים ל-$A$. הוספת tuple אחד משנה את HD מ-0 ל-**10**, שזה כל הטווח. ה-EM מכויל לפי $\Delta=1$, ולכן ההבטחה בפועל היא $10\varepsilon$ במקום $\varepsilon$.

### דוגמה 3: גם primary key לבד שובר את החסם
$D=\{(Dana,F)\}$ ו-$D'=D\cup\{(Dana,M)\}$. אף אחד מהשניים לא certain, ו-$HD$ משתנה מ-0 ל-2. כאן החסם הוא 2 לכל היותר (ראו סעיף 4).

### בעיות נוספות ב-CQA
- **מושג השכנות:** ב-DB לא עקבי ישות אחת היא לרוב block שלם. שכנות ברמת ישות מגדילה את הסנסיטיביות לפי גודל ה-block (group privacy).
- **Coverage:** ‏$|Q'(p(D))|$ לא מוגדר עבור aggregates תחת CQA, כי הסמנטיקה היא טווח $[glb,lub]$.
- **צד חיובי:** עם FO-rewriting, $Q'$ נקבעת רק לפי $Q$ ו-$\Sigma$, ולא לפי $D$, ולכן היא ציבורית. ב-refinement, לעומת זאת, $Q'=M(Q,C,D)$ מדליפה מידע, וההוכחה מתייחסת אליה כקבועה.

---

## 3. בעיות בהוכחות שתקפות גם בלי CQA

### Prop 4.2 (HD)
- החסם $\Delta\le1$ נכון עבור שאילתות SP קבועות ודומיין ציבורי.
- ניסוח Case 1 סותר את עצמו ("המכנה משתנה ב-1" וגם "$t$ לא שייך ל-$V$"). בפועל האיבר לא משתנה.
- `buckets(D[A])` הוא active domain. הוא צריך להיות $Dom(A)$ ציבורי.
- הטווח הנכון הוא $HD\le|Dom(A)|$, ולא $|p(D)|$.
- צריך לכתוב במפורש שהמקרה של הסרה סימטרי (WLOG).

### Prop 4.5 (Usefulness)
- **הטענה $GS_{TVD}=1/|D|$ שגויה.** דוגמה: $|D|=1000$ ו-$p(D)=\{s\}$. מוסיפים $t$ שמקיים את $p$ עם ערך שונה ב-$A$, ו-$TVD(D,p(D))$ משתנה בערך ב-0.5. בנוסף, סנסיטיביות גלובלית לא יכולה להיות תלויה ב-$|D|$.
- איבר (i) חסום ב-$2/|D|$, אבל בשורת הסיכום הוא נכתב כ-2.
- ב-(10) מופיע $|Q(p(D))|/(|D|+1)$ במקום $|Q(p(D))|/(|D|(|D|+1))$. החסם עדיין מתקיים, אבל הוא רופף מאוד.
- $\Delta\le4$ עם טווח $[0,2]$ נכון טכנית אבל חסר ערך: ה-EM בוחר באופן כמעט אחיד.
- טענת הטווח $2|p(D)|^2/|D|$ לא נובעת מההגדרות. מה שנובע הוא $2|p(D)|/|D|$.
- Representativeness מוגדר כ-TVD, אבל בסעיף 3.2 הוא מוגדר כ-$1-TVD$.

### ניהול התקציב (Algorithms 1–2)
- ב-Alg 2: ‏$k$ איטרציות, כל אחת עם Laplace של $\varepsilon/k$ ו-EM עם תקציב שלא צוין. ביחד זה עובר את $\varepsilon/2$.
- לזוג ההיסטוגרמות $(H_Q,H_{Q'})$ יש L1-sensitivity 2, ולכן $Lap(1/\varepsilon)$ נותן $2\varepsilon$.
- ה-COH הרועשים שבהגדרת הבעיה לא נספרים בתקציב.
- ל-DiversityScore ולמכפלה $HD\times Div$ אין ניתוח סנסיטיביות.
- העלות של One-shot top-$\tau$ היא בערך $\tau$ פעמים התקציב לבחירה בודדת, וזה לא מופיע בחישוב.
- פרסום ה-noisy score לא מכוסה בהבטחה של ה-EM. צריך Report-Noisy-Max או תקציב נוסף.
- יש אי-התאמה בין הטקסט ("EM לכל תכונה") לפסאודו-קוד. השורה $C\leftarrow C-H_i$ גם לא מסירה את שאר המועמדים של אותה תכונה.

---

## 4. ההצעה

### 4.1 להגביל את ההיקף ל-primary keys עם שאילתות SP
- $Q'$ = certain answers תחת primary keys. ‏$Q$ היא selection שמחזירה tuples שלמים, בלי projection.
- זה המקרה הסטנדרטי בספרות של CQA, והוא FO-rewritable, ולכן $Q'$ ציבורית:

```sql
Q': SELECT c.* FROM Candidates c
    WHERE <φ(c)>
      AND NOT EXISTS (SELECT 1 FROM Candidates u
                      WHERE u.ID = c.ID AND u <> c)
```

  כלומר, tuple הוא certain אם ורק אם הוא מקיים את $\varphi$ והוא לבד ב-block שלו.
- **ההרחבה ל-FDs:** מניחים חסם ציבורי $d$ על גודל block עקבי, ואז $\Delta\le d+1$.

### 4.2 דוגמה: טבלת מועמדים אחרי איחוד של שתי מערכות HR

| ID | Gender | Degree | Years |
|---|---|---|---|
| 1 | F | MSc | 5 |
| 2 | M | BSc | 7 |
| 2 | M | MSc | 7 |
| 3 | F | PhD | 4 |
| 4 | M | MSc | 6 |
| 4 | F | MSc | 6 |
| 5 | F | MSc | 8 |

`Q: SELECT * WHERE Degree IN ('MSc','PhD') AND Years >= 5`

- $Q(D)$ = ‏{1, 2/MSc, 4/M, 4/F, 5}, וההיסטוגרמה היא F=3, M=2.
- יש 4 repairs. ‏$Q'(D)$ = ‏{1, 5}, וההיסטוגרמה היא F=2, M=0.
- $HD_{cnt}=|3-2|+|2-0|=3$. ההסבר: "במעבר לתשובות הוודאיות נעלמו בעיקר גברים".

### 4.3 HD מבוסס counts וחסם הסנסיטיביות

$HD_{cnt}=\sum_V |H_{Q(p(D))}(V)-H_{Q'(p(D))}(V)|$

**טענה:** תחת primary keys, $\Delta_{HD_{cnt}}\le 2$. מוסיפים tuple $t$ עם מפתח $k$. רק ה-block של $k$ מושפע:

| t שנוסף (בדוגמה) | מצב ה-block | מה קורה | שינוי |
|---|---|---|---|
| (6, M, MSc, 9) | ריק | $t$ נכנס גם ל-$Q$ וגם ל-$Q'$, באותו bucket | 0 |
| (1, F, MSc, 6) | $\{s\}$ | $t$ נכנס ל-$Q$, ‏$s$ יוצא מ-$Q'$ | ≤ 2 |
| (4, M, PhD, 6) | לפחות 2 tuples | $t$ נכנס רק ל-$Q$ | ≤ 1 |

הנקודה: תחת primary key, block עקבי מכיל tuple אחד בדיוק, ולכן לכל היותר tuple אחד מאבד את הוודאות שלו. ב-FD, לעומת זאת, block עקבי יכול להיות גדול (דוגמה 1).

היתרון על הגרסה הנוכחית: הטווח הוא עד $|p(D)|$ ולא עד $|Dom(A)|$, כך שה-EM באמת מבחין בין מועמדים.

### 4.4 תיקונים נוספים
1. **Usefulness:** להוריד את הנרמול ב-$|D|$ ($\Delta_{Coverage_{cnt}}\le3$ תחת primary keys). את Representativeness להוציא מהציון הפרטי, או לנסח מחדש עם ניתוח סנסיטיביות.
2. **טבלת תקציב:** $\varepsilon=\varepsilon_{views}+\varepsilon_{select}+\varepsilon_{hist}$, כולל ה-COH, ומשפט composition אחד.
3. **בדיקה ממוחשבת:** לבדוק ביסודיות זוגות שכנים במסדי נתונים אקראיים קטנים עבור כל פונקציית ציון.

### 4.5 מה ההגבלה מוציאה מההיקף
- **Projection:** הסנסיטיביות תלויה בגודל ה-block.
- **Joins:** ‏tuple אחד יכול לגעת בהרבה שורות תוצאה.
- **Aggregates תחת CQA:** הסמנטיקה שם היא טווח. אצלנו ה-aggregate מחושב מעל קבוצת השורות הוודאיות.

---

## 5. מיקום בספרות

- **CQA:** התחום התחיל ב-PODS 1999, ומוטיבציית הדגל שלו היא data integration. ראו [Bertossi, survey](https://www.researchgate.net/publication/333840185_Database_Repairs_and_Consistent_Query_Answering_Origins_and_Further_Developments) ו-[CQA for primary keys with counting](https://arxiv.org/pdf/2211.04134).
- **הסברים ו-repairs:** [Salimi & Bertossi](https://ar5iv.labs.arxiv.org/html/1404.6857), [Bertossi & Pardal 2025](https://arxiv.org/html/2511.15623v1). אף אחת מהעבודות לא עוסקת בפרטיות.
- **DP על נתונים לא עקביים:** [Computing Inconsistency Measures Under DP](https://arxiv.org/abs/2502.11009v2) (Mohapatra, Gilad, He, Kimelfeld, SIGMOD 2025) משתמש ב-conflict graph ומתמודד עם הסנסיטיביות שתלויה בדרגה. הטכניקות שלהם רלוונטיות להרחבה ל-FDs. ראו גם [PrivateClean](https://amplab.cs.berkeley.edu/publication/privateclean-data-cleaning-and-differential-privacy) ו-[Kamino](https://ar5iv.labs.arxiv.org/html/2012.15713).
- **Fairness:** ‏data cleaning אוטומטי יכול לפגוע ב-fairness: S. Guha, F. A. Khan, J. Stoyanovich, S. Schelter, *Automated Data Cleaning Can Hurt Fairness in Machine Learning-based Decision Making*, ICDE 2023, [doi:10.1109/ICDE55515.2023.00303](https://doi.org/10.1109/ICDE55515.2023.00303). גרסה מורחבת: TKDE 2024, ‏[doi:10.1109/TKDE.2024.3365524](https://doi.org/10.1109/TKDE.2024.3365524).
- **הפער:** לא נמצאה עבודה על הסברים פרטיים להבדל בין $Q$ לבין התשובות הוודאיות שלה. החיפוש היה מוגבל.

### המלצה
1. להשאיר את ה-refinement כ-use case הראשי.
2. לנסח את המודל כמסגרת כללית להסבר ההבדל בין שתי שאילתות (Algorithm 1 כבר כללי).
3. להוסיף סעיף CQA עם primary keys ו-$\Delta\le2$, ואחריו הרחבה ל-FDs עם חסם דרגה ציבורי.
4. סיכונים: מקרה ה-primary key עם SP פשוט מדי מבחינת CQA, ולכן החידוש צריך להיות בצד ה-DP. בנוסף, צריך להיזהר שה-CQA לא יפזר את הפוקוס של המאמר.

</div>
