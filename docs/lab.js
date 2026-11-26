const projects = Array.from(document.querySelectorAll(".project"));
function openLinkedProject() {
  const project = projects.find((item) => "#" + item.id === location.hash);
  if (project) {
    project.open = true;
    project.scrollIntoView({ block: "start" });
  }
}
window.addEventListener("hashchange", openLinkedProject);
window.addEventListener("DOMContentLoaded", openLinkedProject);
for (const link of document.querySelectorAll(".orbit-node")) {
  link.addEventListener("click", () => {
    const target = document.getElementById(link.hash.slice(1));
    target.open = true;
  });
}
const instrument = document.querySelector(".instrument");
const canTilt = matchMedia("(pointer: fine) and (prefers-reduced-motion: no-preference)");
instrument.addEventListener("pointermove", (event) => {
  if (!canTilt.matches) return;
  const box = instrument.getBoundingClientRect();
  const x = (event.clientX - box.left) / box.width - 0.5;
  const y = (event.clientY - box.top) / box.height - 0.5;
  instrument.style.setProperty("--yaw", (x * 13).toFixed(1) + "deg");
  instrument.style.setProperty("--pitch", (-y * 10).toFixed(1) + "deg");
});
instrument.addEventListener("pointerleave", () => {
  instrument.style.removeProperty("--yaw");
  instrument.style.removeProperty("--pitch");
});
