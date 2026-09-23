import { HttpError } from "./errors.js";

export function mountCircleRoutes(app, { service, requireLogin, route, isOps, simulator }) {
  const requireOps = (req, res, next) =>
    isOps(req.phone) ? next() : res.status(403).json({ error: "دسترسی ندارید." });

  app.get("/api/plans", (req, res) => res.json({ plans: service.planSummaries(), simulator }));

  app.get(
    "/api/eligibility",
    requireLogin,
    route(async (req, res) => res.json(await service.eligibility(req.phone))),
  );

  app.get(
    "/api/circles",
    requireLogin,
    route((req, res) => res.json({ circles: service.myCircles(req.phone), ops: isOps(req.phone) })),
  );

  app.post(
    "/api/circles/join",
    requireLogin,
    route(async (req, res) => {
      if (req.body.accept !== true) throw new HttpError(400, "برای عضویت باید شرایط طرح را بپذیرید.");
      const joined = await service.join({
        phone: req.phone,
        planId: req.body.planId,
        payMethod: req.body.payMethod,
        nonce: req.body.nonce,
      });
      res.status(201).json(joined);
    }),
  );

  app.get(
    "/api/circles/:id",
    requireLogin,
    route((req, res) => res.json(service.circleView(req.phone, req.params.id, { ops: isOps(req.phone) }))),
  );

  app.post(
    "/api/circles/:id/pay",
    requireLogin,
    route(async (req, res) => res.status(201).json(await service.startCheckout({ phone: req.phone, circleId: req.params.id }))),
  );

  app.get(
    "/api/checkouts/:id",
    requireLogin,
    route((req, res) => res.json(service.getCheckout(req.phone, req.params.id))),
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

  app.get("/api/ops/circles", requireLogin, requireOps, (req, res) => res.json({ circles: service.listCircles() }));

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
