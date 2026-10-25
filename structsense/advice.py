"""Plain-language repair guidance. This is a first-look guide, NOT a structural engineering design."""

ELEMENTS = ['Wall', 'Column', 'Beam', 'Slab', 'Foundation']

INFO = {
    'Wall': dict(name='Wall (infill / partition)', role='Fills the space between columns and beams. It mostly carries its own weight, not the building.',
                 why='Cracks here are usually caused by shrinkage, temperature changes or small movements. Stair-step or diagonal cracks can point to settlement of the foundation.'),
    'Column': dict(name='Column', role='Carries the weight of the floors above straight down to the foundation. It is one of the most important parts of the structure.',
                   why='Cracks in a column can mean overload, crushing or corroded steel. Treat them as serious even when they look small.'),
    'Beam': dict(name='Beam', role='A horizontal member that carries floor and slab loads sideways to the columns.',
                 why='Thin vertical cracks near the middle are common bending cracks. Diagonal cracks near the ends (supports) can mean shear stress and need an engineer.'),
    'Slab': dict(name='Slab / ceiling', role='The flat floor or roof plate that spreads loads to the beams.',
                 why='Fine map-like cracks are often drying shrinkage. Long cracks along beams, sagging, or water stains need checking.'),
    'Foundation': dict(name='Foundation / plinth', role='Spreads the whole weight of the building into the ground.',
                       why='Cracks that grow, together with tilting doors or walls, can mean the ground is settling. This is urgent.'),
}

CAUSE = {
    'horizontal': 'Horizontal cracks often come from sideways pressure, bending, or rusting steel inside the concrete.',
    'vertical': 'Vertical cracks are often caused by shrinkage or temperature movement, or by settlement under one end.',
    'diagonal': 'Diagonal cracks often come from shear stress or uneven settlement of the foundation.',
    'branching': 'Many branching cracks usually mean surface drying shrinkage, but can also come from chemical reaction in the concrete (ASR).',
}

STEPS = {
    'ok': ['Brush out dust and loose material from the crack.',
           'Seal it with a flexible crack filler or elastomeric paint so water cannot get in.',
           'Write the date and measure the width, then check again in 3 months.'],
    'warn': ['Mark both ends of the crack with a pencil and write the date, so you can see if it grows.',
             'Cut a small V-groove along the crack and clean out the dust.',
             'If the crack is dry and not moving, fill it with epoxy or polymer mortar. If it moves or leaks, use a flexible polyurethane sealant.',
             'Find and fix the cause (leaking pipe, poor drainage, nearby vibration), then re-measure after 1 month.'],
    'crit': ['Limit loads and keep people away from the area until it has been checked.',
             'Call a structural engineer to inspect it before doing any repair.',
             'Typical repairs are epoxy injection, stitching with metal staples, or wrapping with carbon-fibre sheets.',
             'If rust stains or exposed steel are visible, the loose concrete must be removed and the steel treated.',
             'Fix crack monitors (tell-tales) across it and record the width every week.'],
    'none': ['Take the photo straight on, in good light, with the camera about 1 metre from the surface.',
             'Put a ruler or coin in the picture so the size can be measured.',
             'If you still suspect a crack, photograph the area again in a month and compare.'],
}


def build(res, element, flags):
    """res = result from vision.analyze, element = part of structure, flags = sensors currently above their warning level."""
    element = element if element in INFO else 'Wall'
    sev = res['severity']
    urgency = {'none': 'Low', 'ok': 'Low', 'warn': 'Medium', 'crit': 'High'}[sev]
    if sev != 'none' and element in ('Column', 'Foundation') and urgency != 'High':
        urgency = 'High' if sev == 'warn' else 'Medium'         # important elements: raise the priority one step
    deform = None
    if flags:
        deform = 'Deformation warning: ' + ', '.join(f"{n} is {v:.2f} {u}" for n, v, u, _ in flags) + \
                 ' on this building. That points to movement, so ask an engineer to check for leaning or settlement.'
        if urgency == 'Low' and sev != 'none': urgency = 'Medium'
    if sev == 'none':
        summary, cause = 'No crack was found in this photo.', 'The surface looks intact, or the photo is too dark, blurry or far away to show a crack.'
        monitor = 'Take a clearer photo of any area you are worried about.'
    else:
        summary = f"{res['label']}: about {res['length_mm']} mm long and up to {res['max_width_mm']} mm wide, found in a {INFO[element]['name'].lower()}."
        cause = CAUSE.get(res['pattern'], CAUSE['vertical'])
        monitor = 'Measure the width again in 1 month. A crack that is getting wider or longer needs an engineer, whatever its size today.'
    return dict(urgency=urgency, summary=summary, cause=cause, steps=STEPS[sev], monitor=monitor, deformation=deform,
                note='This is a first-look guide from a photo, not an engineering report. A photo cannot measure leaning or bending, so confirm serious cases with a structural engineer.',
                element=dict(key=element, **INFO[element]))
