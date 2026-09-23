import { HttpError } from "./errors.js";

export function mountCircleRoutes(app, { service, reports, requireLogin, route, isOps, simulator }) {
  const requireOps = (req, res, next) =>
    isOps(req.phone) ? next() : res.status(403).json({ error: "دسترسی ندارید." });

  app.get(
    "/api/plans",
    route(async (req, res) => res.json({ plans: await service.planSummaries(), simulator })),
  );

  app.get(
    "/api/eligibility",
    requireLogin,
    route(async (req, res) => res.json(await service.eligibility(req.phone))),
  );

  app.get(
    "/api/circles",
    requireLogin,
    route(async (req, res) => res.json({ circles: await service.myCircles(req.phone), ops: isOps(req.phone) })),
  );

  app.post(
    "/api/circles/join",
    requireLogin,
    route(async (req, res) => {
      if (req.body.accept !== true) throw new HttpError(400, "برای عضویت باید شرایط طرح را بپذیرید.");
      const joined = await service.join({ phone: req.phone, planId: req.body.planId, nonce: req.body.nonce });
      res.status(201).json(joined);
    }),
  );

  app.get(
    "/api/circles/:id",
    requireLogin,
    route(async (req, res) => {
      const ops = isOps(req.phone);
      res.json({ ...(await service.circleView(req.phone, req.params.id, { ops })), ops });
    }),
  );

  app.post(
    "/api/circles/:id/seen",
    requireLogin,
    route(async (req, res) => {
      await service.markSeen({ phone: req.phone, circleId: req.params.id, month: req.body.month });
      res.json({ ok: true });
    }),
  );

  app.post(
    "/api/circles/:id/leave",
    requireLogin,
    route(async (req, res) => {
      await service.leave({ phone: req.phone, circleId: req.params.id });
      res.json({ ok: true });
    }),
  );

  app.post(
    "/api/circles/:id/pay",
    requireLogin,
    route(async (req, res) =>
      res.status(201).json(await service.startCheckout({ phone: req.phone, circleId: req.params.id })),
    ),
  );

  app.get(
    "/api/checkouts/:id",
    requireLogin,
    route(async (req, res) => res.json(await service.getCheckout(req.phone, req.params.id))),
  );

  // With the real gateway Digipay confirms the payment server-to-server; the
  // simulator lets the mock payment page do it.
  app.post(
    "/api/checkouts/:id/complete",
    requireLogin,
    route(async (req, res) => {
      if (!simulator) throw new HttpError(404, "مسیر پیدا نشد.");
      const action = req.body.action === "pay" ? "pay" : "cancel";
      res.json(await service.completeCheckout({ phone: req.phone, id: req.params.id, action }));
    }),
  );

  // ---------- admin panel ----------

  app.get(
    "/api/ops/overview",
    requireLogin,
    requireOps,
    route(async (req, res) => res.json(await reports.overview())),
  );

  app.get(
    "/api/ops/circles",
    requireLogin,
    requireOps,
    route(async (req, res) => res.json({ circles: await reports.circles() })),
  );

  app.get(
    "/api/ops/circles/:id",
    requireLogin,
    requireOps,
    route(async (req, res) => res.json(await reports.circle(req.params.id))),
  );

  app.get(
    "/api/ops/debtors",
    requireLogin,
    requireOps,
    route(async (req, res) => res.json({ debtors: await reports.debtors() })),
  );

  app.get(
    "/api/ops/events",
    requireLogin,
    requireOps,
    route(async (req, res) =>
      res.json({ events: await reports.events({ limit: req.query.limit, kind: req.query.kind || undefined }) }),
    ),
  );

  app.post(
    "/api/ops/circles/:id/fill",
    requireLogin,
    requireOps,
    route(async (req, res) => {
      await service.fillWithBots(req.params.id);
      res.json({ ok: true });
    }),
  );

  app.post(
    "/api/ops/circles/:id/close-month",
    requireLogin,
    requireOps,
    route(async (req, res) => res.json(await service.closeMonth(req.params.id))),
  );
}
