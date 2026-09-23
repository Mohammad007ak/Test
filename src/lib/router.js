import { useCallback, useEffect, useState } from "react";

// Routes live in the URL hash so a refresh or a shared link lands on the
// same screen:
//   (empty)                 home, guaranteed plans
//   #/family                home, family funds
//   #/manage/<id>/<tab>     managing a family fund
//   #/view/<id>             a family fund as its members see it
//   #/circle/<id>           a guaranteed-plan circle (waiting room or running)
//   #/checkout/<id>         the payment page
//   #/ops                   operator tools
//
// Each history entry remembers how deep inside the app it is, so "back"
// can return to the previous screen when there is one, and otherwise to
// the screen's parent (e.g. a shared link, or the mini-app opened straight
// on a circle).
const PAGES = ["family", "manage", "view", "circle", "checkout", "ops"];

function parseRoute() {
  const [, page, id, tab] = window.location.hash.split("/");
  return PAGES.includes(page) ? { page, id, tab } : { page: "home" };
}

const hrefFor = (page, id, tab) =>
  page === "home"
    ? window.location.pathname + window.location.search
    : `#/${page}${id ? `/${id}` : ""}${tab ? `/${tab}` : ""}`;

export function useRoute() {
  const [route, setRoute] = useState(parseRoute);

  useEffect(() => {
    const sync = () => setRoute(parseRoute());
    window.addEventListener("popstate", sync);
    window.addEventListener("hashchange", sync);
    return () => {
      window.removeEventListener("popstate", sync);
      window.removeEventListener("hashchange", sync);
    };
  }, []);

  // go(page, id, tab, { replace }) — replace is for moves that shouldn't
  // leave a step behind: switching tabs, or leaving a finished payment.
  const go = useCallback((page, id, tab, { replace = false } = {}) => {
    const depth = (window.history.state?.depth ?? 0) + (replace ? 0 : 1);
    window.history[replace ? "replaceState" : "pushState"]({ depth }, "", hrefFor(page, id, tab));
    setRoute(parseRoute());
    if (!replace) window.scrollTo({ top: 0 });
  }, []);

  const back = useCallback(
    (parent = "home", id) => {
      if ((window.history.state?.depth ?? 0) > 0) window.history.back();
      else go(parent, id, undefined, { replace: true });
    },
    [go],
  );

  return [route, go, back];
}
